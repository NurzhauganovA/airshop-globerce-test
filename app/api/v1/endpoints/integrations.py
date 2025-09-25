from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status, Form, Query, Request
from redis.asyncio import Redis
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.controllers import merchant_controller, transactions_controller
from app.controllers.internal import user_controller
from app.controllers.transactions_controller import get_card_request_by_id
from app.core import security
from app.core.config import settings
from app.core.database import get_db, get_async_db_session
from app.core.redis_client import get_redis_client
from app.models.internal_model import User, EmployeeProfile
from app.schemas.airlink_schemas import (
    AirlinkResponseSchema,
    CreateOrderByAirlinkAndPhoneNumberPayload,
)
from app.schemas.integrations import MerchantOnboardRequest, MerchantOnboardResponse
from app.schemas.loanrequest_schemas import (
    MFOHookSchema,
    MFOHookResponseSchema,
    LoanOfferCreateSchema,
)
from app.services.fpay.constants import FreedomP2PPaymentStatuses
from app.services.fpay.freedom_p2p import SetPaymentStatusFreedomP2PService
from app.services.order.idempotency_service import (
    OrderCreationIdempotencyService,
    OrderIdempotencyKey,
)
from app.services.saleor import SaleorService

# from app.worker import create_fpay_config_task, create_mfo_config_task, create_saleor_warehouse_task


router = APIRouter()

ss = SaleorService(
    saleor_api_url=settings.SALEOR_GRAPHQL_URL,
    saleor_api_token=settings.SALEOR_API_TOKEN,
)


@router.post(
    "/register-merchant",
    response_model=MerchantOnboardResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_merchant(
        *,
        db: AsyncSession = Depends(get_async_db_session),
        merchant_in: MerchantOnboardRequest,
        current_user: User = Depends(security.get_current_technical_user_basic_auth),
):
    """
    Onboard a new merchant with their legal details, employees, address,
    and default payment methods.

    **This endpoint requires technical user authentication via HTTP Basic Auth.**
    """
    validated = merchant_in.model_validate(merchant_in)
    # 1. Create the merchant.

    new_merchant = await merchant_controller.create_merchant_async(
        db=db, merchant=merchant_in.to_db_model()
    )

    # Create user and employee profile bind it to merhcant
    new_user = await user_controller.get_or_create_with_phone_async(db=db, phone_number=merchant_in.phone)

    new_user.is_merchant = True
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    # Create an EmployeeProfile instance from the request data
    employee_profile_data = EmployeeProfile(
        user_id=new_user.id,
        first_name=validated.employee.first_name,
        middle_name=validated.employee.middle_name,
        last_name=validated.employee.last_name,
        profile_id=validated.employee.profile_id,
        external_id=validated.employee.external_id,
    )
    await merchant_controller.create_employee_for_merchant_async(
        db=db,
        merchant=new_merchant,
        employee=employee_profile_data,  # Pass the EmployeeProfile object
    )

    # 3. Setup default payment methods for the new merchant.
    await merchant_controller.setup_default_payment_methods_async(db=db, merchant=new_merchant)

    # 4. Trigger asynchronous tasks (commented out for now)
    # for mpm in merchant_payment_methods:
    #     # The `base_method` will be lazy-loaded by SQLAlchemy here
    #     # Call future celery task to create MFO config
    #     if mpm.base_method.loan_type:
    #         create_mfo_config_task.delay(merchant_payment_method_id=mpm.id)
    #
    #     # Call future celery task to create FPAY config
    #     if mpm.base_method.type == 'CARD':
    #         create_fpay_config_task.delay(merchant_payment_method_id=mpm.id)

    # Call future celery task to create warehouse in Saleor
    # if address_data.type == "WAREHOUSE":
    #     create_saleor_warehouse_task.delay(
    #         merchant_id=merchant_address.merchant_id, address_id=merchant_address.address_id
    #     )

    await db.commit()
    await db.refresh(new_merchant)

    return {
        "status": "success",
        "merchant_id": new_merchant.id,
        "message": "Merchant created successfully",
    }


@router.post("/loan-requests/{loan_request_id}", response_model=MFOHookResponseSchema)
async def update_loan_request(
        loan_request_id: str,
        request: MFOHookSchema,
        db: Session = Depends(get_db),
) -> MFOHookResponseSchema | None:
    """
    Method for updating loan requests with status or/and offers and inform about issuance
    """
    request_status = request.status

    if request_status not in ("APPROVED", "REJECTED", "ISSUED"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid status. Must be one of: 'APPROVED', 'REJECTED', 'ISSUED'.",
        )

    loan_request_repository = transactions_controller.load_request_controller
    loan_request = loan_request_repository.get(db=db, id=loan_request_id)

    if not loan_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Loan request not found.",
        )

    if request_status == "APPROVED":
        offers = request.offers
        if not offers or len(offers) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Offers must be provided when status is APPROVED.",
            )

        else:
            offers = [
                LoanOfferCreateSchema(
                    loan_request_id=str(loan_request.id),
                    amount=offer.principal,
                    period=offer.period,
                    loan_type=offer.loan_type,
                )
                for offer in offers
            ]
            transactions_controller.load_offer_controller.bulk_create(
                db=db, many_obj=offers
            )

    loan_request = loan_request_repository.update(
        db=db, db_obj=loan_request, obj_in={"status": request_status}
    )

    return MFOHookResponseSchema(
        reference_id=loan_request.id,
        status=loan_request.status,
    )


@router.patch("/card-requests/{card_request_id}")
async def update_card_request(
        cart_request_id: str,
        pg_order_id: str = Form(...),
        pg_reference: str = Form(...),
        pg_card_pan: str = Form(...),
        pg_payment_date: str = Form(...),
        pg_result: int = Form(...),
        pg_can_reject: int = Form(...),
        pg_ps_full_amount: float = Form(...),
        pg_net_amount: float = Form(...),
        db: Session = Depends(get_db),
):
    """
    Method for updating card requests with status and inform about processing
    """
    card_request = get_card_request_by_id(db, card_request_id=cart_request_id)

    if not card_request:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Card request not found",
        )

    card_request.pg_order_id = pg_order_id
    card_request.pg_reference = pg_reference
    card_request.pg_card_pan = pg_card_pan
    card_request.pg_payment_date = pg_payment_date
    card_request.pg_result = pg_result
    card_request.pg_can_reject = pg_can_reject
    card_request.pg_ps_full_amount = pg_ps_full_amount
    card_request.pg_net_amount = pg_net_amount

    if pg_result == 0:
        card_request.status = "FAILED"
    elif pg_result == 1:
        card_request.status = "SUCCESS"
    else:
        card_request.status = "INTERUPTED"

    db.add(card_request)
    db.commit()
    db.refresh(card_request)

    return 200


@router.get(
    "/list-airlinks-by-merchant/",
    status_code=status.HTTP_200_OK,
    response_model=list[AirlinkResponseSchema],
)
async def list_airlinks_by_merchant(
        merchant_bin: str | None = Query(None, description="Filter by merchant BIN"),
        db: Session = Depends(get_db),
) -> list[AirlinkResponseSchema] | None:
    """
    List all airlinks for a specific merchant.
    """
    if not merchant_bin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Merchant BIN is required.",
        )

    airlinks = merchant_controller.get_airlinks_by_merchant_bin(
        db=db,
        merchant_bin=merchant_bin,
    )
    if not airlinks:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No airlinks found for the given merchant BIN.",
        )

    return airlinks


@router.post(
    "/integrations/order",
    status_code=status.HTTP_200_OK,
    dependencies=[
        Depends(security.get_current_technical_user_basic_auth)
    ]
)
async def create_order_by_airlink_and_phone_number(
        payload: CreateOrderByAirlinkAndPhoneNumberPayload = Depends(),
        db: Session = Depends(get_db),
        redis: Redis = Depends(get_redis_client)
) -> dict[str, Any]:
    """
    Creates a Saleor checkout and an internal transaction record from an Airlink.
    """

    key = OrderIdempotencyKey(
        phone_number=payload.phone_number,
        internal_order_id=payload.airlink_id,
    )
    service = OrderCreationIdempotencyService.create_service(redis=redis, key=key)
    result = await service.execute(
        key=key,
        db=db,
        saleor_service=ss,
        phone_number=payload.phone_number,
        airlink_id=payload.airlink_id,
    )
    return result


@router.post(
    "/remote-payment/{order_id}/update",
    dependencies=[
        Depends(security.get_current_technical_user_basic_auth)
    ]
)
async def update_order_status(
        order_id: str,
        request: Request,
        db: Session = Depends(get_db),
):
    request_body = await request.json()
    status_code = request_body.get("status", {}).get("code", "")
    receipt_number = request_body.get("payment", {}).get("receiptNumber", "")

    if status_code in ["SUCCESS", "HOLD", ]:
        payment_status = FreedomP2PPaymentStatuses.HOLD
    elif status_code == ["CANCELLED"]:
        payment_status = FreedomP2PPaymentStatuses.CANCELLED
    else:
        payment_status = None

    if payment_status:
        service = SetPaymentStatusFreedomP2PService(db=db, freedom_order_id=order_id)
        service.process(status=payment_status, receipt_number=receipt_number)

    return {
        "code": status.HTTP_200_OK,
        "status": "SUCCESS"
    }
