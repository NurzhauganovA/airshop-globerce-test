import asyncio
import mimetypes
import os
import shutil
import tempfile
from io import BytesIO

import requests
from fastapi import UploadFile

from app.controllers.airlink_controller import AirlinkController
from app.controllers.transactions_controller import (
    get_transaction_by_id,
    create_card_payment_request,
    get_loan_request_by_mfo_uuid,
    get_loan_request_by_id,
    load_offer_controller,
    transactions_controller,
)
from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.s3_client import s3_client
from app.graphql.generated_client import TransactionCreateInput, MoneyInput
from app.graphql.generated_client.client import SaleorClient
from app.models.internal_model import Airlink, AirlinkCheckoutItem
from app.schemas.freedom import FPayCardPaymentRequestDto
from app.schemas.loanrequest_schemas import (
    LoanOfferCreateSchema,
)
from app.services.fpay.freedom_p2p import UnholdPaymentFreedomP2PService
from app.services.fpay.freedom_pay import FreedomPayService
from app.services.mfo.freedom_mfo import (
    FreedomMfoService,
    ApplyLoanRequest,
    AdditionalInformationSchema,
    GoodsSchema,
)
from app.services.saleor import SaleorService

mfo_service = FreedomMfoService(settings.FREEDOM_MFO_HOST)
airlink_controller = AirlinkController(Airlink)
saleor_service = SaleorService(settings.SALEOR_GRAPHQL_URL, settings.SALEOR_API_TOKEN)


async def _complete_transaction(transaction_id: str):
    db = SessionLocal()
    transaction = get_transaction_by_id(db=db, transaction_id=transaction_id)
    if transaction.status == "COMPLETED":
        if not transaction.synced:
            saleor_transaction_response = await saleor_service.client.create_transaction_for_order(
                order_id=transaction.saleor_order_id,
                transaction_input=TransactionCreateInput(
                    name="Fastback transaction",
                    message=f"Transaction id {transaction.id}, payment method {transaction.payment_method.base_method.type}",
                    amountCharged=MoneyInput(amount=transaction.amount, currency="KZT"),
                ),
            )

            if saleor_transaction_response.transaction_create.errors:
                raise Exception(saleor_transaction_response.transaction_create.errors)
            transaction.synced = True
            db.add(transaction)
            db.commit()
            db.close()


async def _get_card_payment_status(transaction_id: str):
    db = SessionLocal()
    transaction = get_transaction_by_id(db=db, transaction_id=transaction_id)
    card_request = transaction.card_requests[0]

    fpay_config = transaction.payment_method.fpay_configs

    if not fpay_config:
        raise ValueError(f"No Freedom Pay Configs for transaction: {transaction.id}")

    print(fpay_config)

    secret_key = fpay_config[0].secret_key
    merchant_id = fpay_config[0].fpay_merchant_id

    if not secret_key or not merchant_id:
        raise ValueError(
            f"No Secret key or Merchant_id for transaction: {transaction.id}"
        )

    pay_service = FreedomPayService(url=settings.FREEDOM_PAY_HOST, token=secret_key)

    request_status = await pay_service.get_status(
        data=FPayCardPaymentRequestDto(
            order_id=transaction.id,
            merchant_id=merchant_id,
            payment_id=card_request.pg_payment_id,
            secret_key=secret_key,
        )
    )

    request_response = request_status.get("response")

    card_request.status = request_response.get("pg_payment_status")

    if card_request.status == "success":
        transaction.status = "COMPLETED"
    if card_request.status == "error":
        transaction.status = "FAILED"

    db.add(card_request)
    db.add(transaction)
    db.commit()
    db.close()


async def _process_mfo_request(loan_request_id: str):
    db = SessionLocal()
    loan_request = get_loan_request_by_id(db=db, loan_request_id=loan_request_id)
    if not loan_request:
        raise ValueError("Not found loan request")

    mfo_config = loan_request.transaction.payment_method.mfo_configs[0]

    if not mfo_config:
        raise ValueError("Not found mfo config")
    try:
        apply_request_response = await mfo_service.send_loan_request(
            request_data=ApplyLoanRequest(
                iin=loan_request.iin,
                mobile_phone=loan_request.mobile_phone,
                product=mfo_config.product_code,
                partner=mfo_config.partner_code,
                channel=settings.FREEDOM_MFO_CHANNEL,
                credit_params={
                    "principal": float(loan_request.transaction.amount),
                    "period": 24,
                },
                additional_information=AdditionalInformationSchema(
                    reference_id=loan_request.transaction.id,
                    success_url=f"{settings.BASE_HOST}status-page",
                    failure_url=f"{settings.BASE_HOST}status-page",
                    hook_url=f"{settings.BASE_HOST}api/v1/loan-request/{loan_request.id}",
                ),
                merchant={
                    "bin": loan_request.transaction.payment_method.merchant.bin,
                    "name": loan_request.transaction.payment_method.merchant.legal_name,
                },
                credit_goods=[
                    GoodsSchema(
                        cost=str(loan_request.transaction.amount),
                        quantity=1,
                        category="Some category",
                    )
                ],
            )
        )

        if apply_request_response.status_code == 202:
            loan_request.status = "PENDING"
            loan_request.mfo_uuid = apply_request_response.json().get("uuid")
            loan_request.raw_json_response = apply_request_response.json()
            db.add(loan_request)
            db.commit()
            db.refresh(loan_request)
            get_loan_request_status.delay(uuid=loan_request.mfo_uuid)

    except Exception as e:
        raise Exception(f"Error During exection {e}")


async def _pull_status_update(uuid: str):
    """
    pull status update from mfo
    """
    db = SessionLocal()

    loan_request = get_loan_request_by_mfo_uuid(db=db, uuid=uuid)

    status_response = await mfo_service.get_offers(uuid=uuid)

    if status_response.is_success:
        loan_request.status = (
            status_response.json().get("result")
            if status_response.json().get("result")
            else "PENDING"
        )
        additional_approved_params = status_response.json().get(
            "additional_approved_params"
        )
        if len(additional_approved_params) > 0 and not loan_request.loan_offers:
            offers = []
            for param in additional_approved_params:
                offer = LoanOfferCreateSchema(
                    loan_request_id=loan_request.id,
                    amount=param.get("principal"),
                    period=param.get("period"),
                    loan_type=param.get("product_type"),
                    suitable=True,
                    outer_id=param.get("product"),
                )
                offers.append(offer)
                load_offer_controller.bulk_create(db=db, many_obj=offers)
        db.add(loan_request)
        db.commit()
        if loan_request.status == "APPROVED" and not loan_request.selected_offer:
            loan_request.transaction.status = "ACTION_REQUIRED"
            loan_request.redirect_url = (
                status_response.json().get("redirect_url")
                if status_response.json().get("redirect_url")
                else None
            )
            db.add(loan_request.transaction)
            db.commit()
        if loan_request.status == "REJECTED":
            loan_request.transaction.status = "FAILED"
            db.add(loan_request.transaction)
            db.commit()
        if loan_request.status == "ISSUED":
            loan_request.transaction.status = "COMPLETED"
            db.add(loan_request.transaction)
            db.commit()
    db.close()


async def _process_card_payment(transaction_id: str):
    """
    process card payment request
    """
    db = SessionLocal()
    transaction = get_transaction_by_id(db, transaction_id=transaction_id)

    if transaction.card_requests:
        card_payment_request = transaction.card_requests[0]
    else:
        card_payment_request = create_card_payment_request(
            db=db, transaction=transaction
        )

    fpay_config = transaction.payment_method.fpay_configs

    if not fpay_config:
        raise ValueError(f"No Freedom Pay Configs for transaction: {transaction.id}")

    print(fpay_config)

    secret_key = fpay_config[0].secret_key
    merchant_id = fpay_config[0].fpay_merchant_id

    if not secret_key or not merchant_id:
        raise ValueError(
            f"No Secret key or Merchant_id for transaction: {transaction.id}"
        )

    pay_service = FreedomPayService(url=settings.FREEDOM_PAY_HOST, token=secret_key)

    payment_response = await pay_service.pay(
        FPayCardPaymentRequestDto(
            order_id=transaction.id,
            merchant_id=merchant_id,
            secret_key=secret_key,
            amount=transaction.amount,
            description=f"Заказ № {transaction.saleor_order_id}",
            result_url=f"{settings.BASE_HOST}/card-request/{card_payment_request.id}",
            success_url=f"{settings.BASE_HOST}/card-request/{card_payment_request.id}",
            failure_url=f"{settings.BASE_HOST}/card-request/{card_payment_request.id}",
        )
    )

    response_body = payment_response.get("response")

    print(response_body)

    if response_body.get("pg_redirect_url"):
        card_payment_request.redirect_url = response_body.get("pg_redirect_url")
        card_payment_request.pg_payment_id = response_body.get("pg_payment_id")
        card_payment_request.pg_order_id = transaction.id
        transaction.status = "ACTION_REQUIRED"
        db.add(transaction)
        db.add(card_payment_request)
        db.commit()
        db.refresh(card_payment_request)
    db.close()


async def _process_quick_airlink(airlink_id: str):
    """
    A Celery task to process a newly created quick airlink.
    """
    db = SessionLocal()
    async with SaleorClient(
            url=settings.SALEOR_GRAPHQL_URL,
            headers={"Authorization": f"Bearer {settings.SALEOR_API_TOKEN}"},
    ) as saleor_client:
        try:
            print(f"Processing quick airlink: {airlink_id}")
            airlink = airlink_controller.get_airlink_by_id(db, airlink_id)
            if not airlink:
                print(f"Airlink with id {airlink_id} not found for processing.")
                return

            # --- Start: Image background removal ---
            original_image_url = airlink.images[0].url
            temp_file_path = None
            try:
                # 1. Download original image and save to a temporary file
                with requests.get(original_image_url, stream=True, timeout=30) as r:
                    r.raise_for_status()
                    content_type = r.headers.get("content-type", "image/jpeg")
                    file_extension = mimetypes.guess_extension(content_type) or ".jpg"

                    with tempfile.NamedTemporaryFile(
                            delete=False, suffix=file_extension
                    ) as tmp_file:
                        shutil.copyfileobj(r.raw, tmp_file)
                        temp_file_path = tmp_file.name

                # 2. Upload for background removal
                remove_bg_url = settings.IMAGE_PROCESSING_URL.replace(
                    "/moderate", "/remove-background-with-shadow"
                )
                with open(temp_file_path, "rb") as f:
                    files = {
                        "formFile": (os.path.basename(temp_file_path), f, content_type)
                    }
                    headers = {"Accept": "image/png"}
                    remove_bg_response = requests.post(
                        remove_bg_url, files=files, headers=headers, timeout=60
                    )

                remove_bg_response.raise_for_status()

                # 3. Get new image from response and upload to S3
                new_image_content = remove_bg_response.content
                new_image_file = BytesIO(new_image_content)
                upload_file = UploadFile(
                    filename="processed.png",
                    file=new_image_file,
                    headers={"content-type": "image/png"},
                )
                new_s3_url = s3_client.upload_file(upload_file, folder="airlink-images")

                # 4. Update airlink image url in DB
                airlink.images[0].url = new_s3_url
                db.add(airlink.images[0])
                db.commit()
                db.refresh(airlink)

            finally:
                # 5. Cleanup temporary file
                if temp_file_path and os.path.exists(temp_file_path):
                    os.remove(temp_file_path)
            # --- End: Image background removal ---

            payload = {"sourceS3Url": "", "sourceURL": airlink.images[0].url}
            image_processing_request = requests.post(
                settings.IMAGE_PROCESSING_URL, json=payload, timeout=40
            )

            image_processing_request.raise_for_status()

            image_data = image_processing_request.json()

            print(image_data)

            airlink.ai_response = image_data

            if image_data.get("risk_value") != "Low" or not image_data.get(
                    "product_name"
            ):
                airlink.moderation_status = "REJECTED"
                db.add(airlink)
                db.commit()
                print(
                    f"Airlink {airlink_id} rejected due to image moderation risk: {image_data.get('risk_value')}"
                )
                return

            """
                
            """

            print("Create product in Saleor")
            product_response = await saleor_client.create_product_for_merchant(
                product_type=settings.LINK_SALEOR_PRODUCT_TYPE,
                merchant_id=airlink.merchant_id,
                category=settings.LINK_SALEOR_CATEGORY_ID,
                name=image_data.get("product_name"),
            )
            if (
                    not product_response.product_create
                    or not product_response.product_create.product
                    or product_response.product_create.errors
            ):
                errors = (
                    product_response.product_create.errors
                    if product_response.product_create
                    else "Unknown error"
                )
                raise Exception(f"Failed to create product in Saleor: {errors}")

            product_id = product_response.product_create.product.id

            print("Create variant in Saleor")

            variant_response = await saleor_client.create_variant_for_product(
                product_id=product_id,
                sku=airlink.id,
                name=image_data.get("product_name_rus"),
            )
            if (
                    not variant_response.product_variant_create
                    or not variant_response.product_variant_create.product_variant
                    or variant_response.product_variant_create.errors
            ):
                errors = (
                    variant_response.product_variant_create.errors
                    if variant_response.product_variant_create
                    else "Unknown error"
                )
                raise Exception(f"Failed to create variant in Saleor: {errors}")

            variant_id = variant_response.product_variant_create.product_variant.id

            print("Add product to channel")

            await saleor_client.add_product_to_channel(
                product_id=product_id, chanel_id=settings.LINK_SALEOR_CHANNEL_ID
            )

            print("Set prices")
            # await saleor_client.variant_set_price(
            #    variant_id=variant_id,
            #    channel_id=settings.LINK_SALEOR_CHANNEL_ID,
            #    price=airlink.planned_price,
            # )

            airlink.checkout_items.append(
                AirlinkCheckoutItem(
                    saleor_variant_id=variant_id,
                    quantity=1,
                    price=airlink.planned_price,
                )
            )

            # Update the airlink status to show it's processed
            airlink.moderation_status = "APPROVED"
            airlink.name = image_data.get("product_name_rus")
            airlink.description = image_data.get("description_rus")
            db.add(airlink)
            db.commit()
            print(f"Finished processing airlink: {airlink_id}. Status set to APPROVED.")

        except Exception as e:
            print(f"Error processing airlink {airlink_id}: {e}")
            # If an error occurs, mark the airlink as FAILED
            if airlink:
                airlink.moderation_status = "FAILED"
                db.add(airlink)
                db.commit()
            db.rollback()
        finally:
            db.close()


@celery_app.task(acks_late=True)
def process_quick_airlink(airlink_id: str):
    """
    Celery task to process a newly created quick airlink.
    """
    asyncio.run(_process_quick_airlink(airlink_id))


@celery_app.task(acks_late=True)
def process_card_payment(transaction_id: str):
    asyncio.run(_process_card_payment(transaction_id))


@celery_app.task(acks_late=True)
def get_loan_request_status(uuid: str):
    asyncio.run(_pull_status_update(uuid=uuid))


@celery_app.task(acks_late=True)
def process_loan_request(loan_request_id: str):
    asyncio.run(_process_mfo_request(loan_request_id=loan_request_id))


@celery_app.task(acks_late=True)
def get_card_payment_status(transaction_id: str):
    asyncio.run(_get_card_payment_status(transaction_id=transaction_id))


@celery_app.task(acks_late=True)
def complete_transaction(transaction_id: str):
    asyncio.run(_complete_transaction(transaction_id=transaction_id))


@celery_app.task(acks_late=True)
def cancel_expired_freedom_p2p_orders():
    db = SessionLocal()
    try:
        transactions_controller.cancel_expired_freedom_p2p_orders(db)
    finally:
        db.close()


@celery_app.task(acks_late=True)
def unhold_freedom_order_payment(freedom_order_reference_id: str) -> None:
    try:
        service = UnholdPaymentFreedomP2PService(freedom_order_reference_id=freedom_order_reference_id)
        result = asyncio.run(service.process())

        if not service.is_payment_unhold_success(result):
            raise Exception(f"Unhold failed for {freedom_order_reference_id}: {result}")

    except Exception as exc:
        # logger.error("Unexpected error while unholding %s", freedom_order_reference_id)
        print(f"Unexpected error while unholding {exc}")
