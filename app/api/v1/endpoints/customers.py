from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query, Header
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlalchemy.orm import Session

from app.controllers import transactions_controller
from app.controllers.airlink_controller import airlink_controller
from app.controllers.internal import (
    customer_controller,
    country_controller,
    city_controller,
    address_controller,
)
from app.controllers.merchant_controller import get_merchant_by_id
from app.controllers.merchant_site_controller import merchant_site_controller
from app.core import security
from app.core.config import settings
from app.core.database import get_db
from app.graphql.generated_client import CheckoutLineInput
from app.graphql.generated_client.client import ProductWhereInput
from app.models.cms_models import MerchantSite
from app.models.internal_model import Airlink
from app.models.internal_model import User, Merchant
from app.pagination.cursor_pagination import (
    CursorParamsWithOutTotal,
    CursorPageWithOutTotal,
)
from app.schemas.address_schema import (
    AddressCustomerInputSchema,
    AddressListModelSchema,
    CountryModelSchema,
    CityModelSchema,
    AddressModelSchema,
)
from app.schemas.airlink_schemas import (
    AirlinkResponseSchema,
    AirlinkImages,
)
from app.schemas.cart_schema import (
    CartSchema,
    CartLineOperationSchema,
    CartItemSchema,
    ShippingMethodSchema,
    CollectionPointSchema,
    CartFullSchema,
    CartAddressSchema,
    CartFullPatchShema,
    CompleteCheckoutRequestSchema,
)
from app.schemas.category_schemas import CategoryListSchema
from app.schemas.integrations import MerchantOnboardResponse
from app.schemas.loanrequest_schemas import SetOfferRequest
from app.schemas.merchant_site_shemas import MerchantSiteSchema, MerchantSiteCarouselItemSchema
from app.schemas.order_schemas import (
    BasePaymentMethodSchema,
    MerchantPaymentMethodSchema,
    OrderProcessPaymentResponse,
)
from app.schemas.order_schemas import (
    OrderByAirlinkResponse,
    CreateOrderByAirlinkRequest,
    CreateOrderResponse,
)
from app.schemas.product_schemas import (
    PaginatedProductsResponse,
    ProductVariantShortSchema,
    ProductShortSchma,
    ProductFullSchema,
)
from app.services.airlink.create_order import CreateOrderByAirlinkService
from app.services.mfo.freedom_mfo import (
    FreedomMfoService,
    SendOTPRequest,
    ValidateOTPRequest,
    PickOfferSchema,
    CreditParams,
)
from app.services.saleor import SaleorService
from app.worker import (
    process_card_payment,
    get_loan_request_status,
    process_loan_request,
    get_card_payment_status,
    complete_transaction,
)

mfo_service = FreedomMfoService(settings.FREEDOM_MFO_HOST)

ss = SaleorService(
    saleor_api_url=settings.SALEOR_GRAPHQL_URL,
    saleor_api_token=settings.SALEOR_API_TOKEN,
)

# We'll use a router for each major group of endpoints
router = APIRouter()


async def _get_site_from_domain(
    x_customer_site_domain: str = Header(..., alias="X-CUSTOMER-SITE-DOMAIN"),
    db: Session = Depends(get_db),
) -> MerchantSite:
    """
    Internal function to get site from domain
    """
    site = merchant_site_controller.get_site_by_preffix(
        db, preffix=x_customer_site_domain
    )
    if not site:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Site with domain '{x_customer_site_domain}' not found.",
        )
    return site


async def get_merchant_from_site_domain(
    site: MerchantSite = Depends(_get_site_from_domain),
) -> Merchant:
    """
    Dependency to get a Merchant from the X-CUSTOMER-SITE-DOMAIN header.
    """
    if not site.merchant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No merchant associated with site '{site.domain}'.",
        )
    return site.merchant


async def get_merchant_site_from_site_domain(
    site: MerchantSite = Depends(_get_site_from_domain),
) -> MerchantSite:
    """
    Dependency to get a MerchantSite from the X-CUSTOMER-SITE-DOMAIN header.
    """
    return site


@router.get(
    "/order-by-airlink/{airlink_id}",
    response_model=OrderByAirlinkResponse,
    tags=["Customer"],
)
async def preview_order_by_airlink(
    airlink_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(security.get_current_user),
):
    """
    Displays information about airlink
    """
    airlink = airlink_controller.get_airlink_by_id(db, airlink_id)
    if not airlink:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Airlink not found"
        )

    # Fetch merchant details and available payment options
    merchant = airlink.merchant
    if not merchant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Merchant not found for this Airlink",
        )

    available_payment_options = []
    for mpm in merchant.merchant_payment_methods:
        if mpm.active and mpm.base_method and mpm.base_method.enabled:
            available_payment_options.append(
                mpm
            )  # Assuming mpm is already a MerchantPaymentMethodSchema compatible object

    # Convert Airlink model to AirlinkResponseSchema
    airlink_response = AirlinkResponseSchema(
        id=airlink.id,
        moderation_status=airlink.moderation_status,
        name=airlink.name,
        description=airlink.description,
        date_start=airlink.date_start,
        date_end=airlink.date_end,
        merchant_id=airlink.merchant_id,
        created_at=airlink.created_at,
        updated_at=airlink.updated_at,
        total_price=(
            airlink.total_price if airlink.total_price is not None else Decimal(0)
        ),
        images=[AirlinkImages(url=img.url, is_main=False) for img in airlink.images],
        public_url=airlink.public_url,
        published=airlink.published,
    )

    # Convert merchant and payment methods to their respective schemas
    merchant_response = MerchantOnboardResponse(
        merchant_id=merchant.id,
        legal_name=merchant.legal_name,
        bin=merchant.bin,
    )

    available_payment_options_response = []
    for mpm in available_payment_options:
        base_method_schema = None
        if mpm.base_method:
            base_method_schema = BasePaymentMethodSchema(
                id=mpm.base_method.id,
                type=mpm.base_method.type,
                loan_type=mpm.base_method.loan_type,
                loan_period_range=str(
                    mpm.base_method.loan_period_range
                ),  # Convert to string
                enabled=mpm.base_method.enabled,
            )
        available_payment_options_response.append(
            MerchantPaymentMethodSchema(
                id=mpm.id,
                merchant=merchant_response,  # Pass the already created merchant_response
                active=mpm.active,
                base_method=base_method_schema,
            )
        )

    # For now, current_payment_method is None as it's a preview
    return {
        "airlink": airlink_response,
        "merchant": merchant_response,
        "availablePaymentOptions": available_payment_options_response,
    }


@router.post(
    "/order-by-airlink/{airlink_id}",
    response_model=CreateOrderResponse,
    tags=["Customer"],
)
async def create_order_from_airlink(
    airlink_id: str,
    request: CreateOrderByAirlinkRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(security.get_current_user),
):
    """
    Creates a Saleor checkout and an internal transaction record from an Airlink.
    This is the first step in the customer's purchase journey.
    The returned `order_id` is the ID of the internal transaction.
    """
    # 1. Validate user
    if current_user.is_merchant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Merchants cannot create orders.",
        )
    if not current_user.customer_profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User does not have a customer profile.",
        )

    airlink = airlink_controller.get(db, id=airlink_id)
    airlink_create_order_service = CreateOrderByAirlinkService(
        airlink=airlink,
        saleor_service=ss,
        payment_method_id=request.payment_method_id,
        customer_id=current_user.customer_profile.id,
        customer_email=current_user.get_email_or_default,
        saleor_channel_id=settings.LINK_SALEOR_CHANNEL_ID
    )

    saleor_order_id = await airlink_create_order_service.create_order()
    airlink_create_order_service.create_transaction(db=db, saleor_order_id=saleor_order_id)

    return {"order_id": saleor_order_id}


@router.post(
    "/orders/{order_id}/process-payment", response_model=OrderProcessPaymentResponse
)
async def process_payment(
    order_id: str,
    current_user: User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    """
    Creates transaction for order, requires payment type
    """
    # 1. Validate user
    if current_user.is_merchant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Merchants cannot process orders.",
        )
    if not current_user.customer_profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User does not have a customer profile.",
        )

    transaction = transactions_controller.get_transaction_by_order_id(
        db, saleor_order_id=order_id
    )

    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cannot find transaction for order",
        )

    # implement order = ss.client.get_order_by_id(order_id)
    # To check if there is a matching customer.id

    match transaction.status:
        case "NEW":
            transactions_controller.set_new_status(
                db, transaction=transaction, new_status="IN_PROGRESS"
            )
            # get payment type
            # if payment type = CARD
            if transaction.payment_method.base_method.type == "CARD":
                process_card_payment.delay(transaction.id)
            elif transaction.payment_method.base_method.type == "LOAN":
                transactions_controller.set_new_status(
                    db, transaction=transaction, new_status="ACTION_REQUIRED"
                )
                return OrderProcessPaymentResponse(
                    status=transaction.status, required_action="FILL_IIN"
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_501_NOT_IMPLEMENTED,
                    detail="Unknown payment type",
                )
            # If it's a card payment, the status remains 'IN_PROGRESS' and no immediate action is required from the user
            return OrderProcessPaymentResponse(status=transaction.status)
        case "ACTION_REQUIRED":
            if transaction.payment_method.base_method.type == "LOAN":
                # Check if IIN is required (e.g., if loan_requests is empty or IIN is not set)
                if (
                    not transaction.loan_requests
                    or not transaction.loan_requests[0].iin
                ):
                    return OrderProcessPaymentResponse(
                        status=transaction.status, required_action="FILL_IIN"
                    )
                # Check if offers need to be chosen
                if (
                    transaction.loan_requests
                    and transaction.loan_requests[0].iin
                    and not transaction.loan_requests[0].selected_offer
                ):
                    return OrderProcessPaymentResponse(
                        status=transaction.status, required_action="CHOOSE_OFFER"
                    )

                if (
                    transaction.loan_requests
                    and transaction.loan_requests[0].iin
                    and transaction.loan_requests[0].selected_offer
                ):
                    get_loan_request_status.delay(
                        str(transaction.loan_requests[0].mfo_uuid)
                    )
                    return OrderProcessPaymentResponse(
                        status=transaction.status,
                        required_action="FOLLOW_REDIRECT_LINK",
                        redirect_url=transaction.loan_requests[0].redirect_url,
                    )
            # If IIN is filled and offer is selected, but still ACTION_REQUIRED, it means further processing is needed
            # This case might indicate an external system interaction or final confirmation
            if transaction.payment_method.base_method.type == "CARD":
                get_card_payment_status.delay(transaction.id)
                return OrderProcessPaymentResponse(
                    status=transaction.status,
                    required_action="FOLLOW_REDIRECT_LINK",
                    redirect_url=transaction.card_requests[0].redirect_url,
                )
        case "COMPLETED":
            complete_transaction(transaction.id)
            return OrderProcessPaymentResponse(status=transaction.status)

    # check if there are transaction for order
    # if no error
    # if transaction status - new then set it to processing
    # icall celery task depending on method base method payment type
    # if payment method type loan - and there are no related loanRequest then set status to action_required and return FILL_IIN
    # if payment method loan and there are loanRequest then check offers if no offers then
    # for processing
    return OrderProcessPaymentResponse(status=transaction.status)


@router.patch("/orders/{order_id}/process-payment")
async def change_payment_type():
    """
    changes payment type for transaction
    """
    pass


@router.post("/orders/{order_id}/process-payment/send-otp")
async def send_otp(
    order_id: str,
    otp_request: SendOTPRequest,
    current_user: User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    """
    Creates transaction for order, requires payment type
    """
    # 1. Validate user
    if current_user.is_merchant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Merchants cannot process orders.",
        )
    if not current_user.customer_profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User does not have a customer profile.",
        )

    transaction = transactions_controller.get_transaction_by_order_id(
        db, saleor_order_id=order_id
    )

    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cannot find transaction for order",
        )
    if not transaction.loan_requests:
        loan_request = transactions_controller.create_loan_payment_request(
            db=db,
            transaction=transaction,
            iin=otp_request.iin,
            mobile_phone=otp_request.phone,
        )

    else:
        loan_request = transaction.loan_requests[0]

    mfo_response = await mfo_service.send_otp(otp_data=otp_request)

    if not mfo_response.status_code:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="MFO Send OTP ERROR, try again later",
        )

    if mfo_response.status_code == 429:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please try again later.",
        )

    return loan_request


@router.post("/orders/{order_id}/process-payment/validate-otp")
async def validate_otp(
    order_id: str,
    otp_request: ValidateOTPRequest,
    current_user: User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    """
    Creates transaction for order, requires payment type
    """
    # 1. Validate user
    if current_user.is_merchant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Merchants cannot process orders.",
        )
    if not current_user.customer_profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User does not have a customer profile.",
        )

    transaction = transactions_controller.get_transaction_by_order_id(
        db, saleor_order_id=order_id
    )

    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cannot find transaction for order",
        )

    loan_request = transaction.loan_requests[0]

    if loan_request.iin != otp_request.iin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Missmatiching IIN"
        )

    mfo_response = await mfo_service.validate_otp(validate_data=otp_request)

    print(mfo_response)

    if not mfo_response.status_code:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="MFO Send OTP ERROR, try again later",
        )

    if mfo_response.status_code == 429:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please try again later.",
        )
    process_loan_request.delay(str(loan_request.id))

    # run apply request
    return loan_request


@router.get("/orders/{order_id}/process-payment/get-offers")
async def get_offers(
    order_id: str,
    current_user: User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    """
    pulls offers for data
    """
    # 1. Validate user
    if current_user.is_merchant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Merchants cannot process orders.",
        )
    if not current_user.customer_profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User does not have a customer profile.",
        )

    transaction = transactions_controller.get_transaction_by_order_id(
        db, saleor_order_id=order_id
    )

    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cannot find transaction for order",
        )
    loan_request = transaction.loan_requests[0]

    if not loan_request.loan_offers:
        # call update_loan_offers task
        get_loan_request_status.delay(str(loan_request.mfo_uuid))
        return []

    return loan_request.loan_offers


@router.post("/orders/{order_id}/process-payment/offer")
async def set_offer(
    request: SetOfferRequest,
    order_id: str,
    current_user: User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    """
    sets offer for transaction
    """
    # 1. Validate user
    if current_user.is_merchant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Merchants cannot process orders.",
        )
    if not current_user.customer_profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User does not have a customer profile.",
        )

    transaction = transactions_controller.get_transaction_by_order_id(
        db, saleor_order_id=order_id
    )

    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cannot find transaction for order",
        )

    loan_request = transaction.loan_requests[0]

    if not loan_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cannot find loan request for order",
        )
    loan_request_offers = loan_request.loan_offers

    if not loan_request_offers:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cannot find loan offers for order, wait until it come",
        )

    for offer in loan_request_offers:
        if offer.id == request.offer_id:
            loan_request.selected_offer = offer.id
            set_offer_response = await mfo_service.set_offer(
                pick_offer_data=PickOfferSchema(
                    reference_id=loan_request.mfo_uuid,
                    product=offer.outer_id,
                    credit_params=CreditParams(
                        period=offer.period, principal=offer.amount
                    ),
                )
            )
            if not set_offer_response.status_code == 200:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="MFO Set Offer ERROR, try again later",
                )

            db.add(loan_request)
            db.commit()
            db.refresh(loan_request)
            break
    return loan_request


@router.patch("/orders/{order_id}/process-payment/offer")
async def change_offer(
    request: SetOfferRequest,
    order_id: str,
    current_user: User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    """
    changes offer for transaction
    """
    # 1. Validate user
    if current_user.is_merchant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Merchants cannot process orders.",
        )
    if not current_user.customer_profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User does not have a customer profile.",
        )

    transaction = transactions_controller.get_transaction_by_order_id(
        db, saleor_order_id=order_id
    )

    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cannot find transaction for order",
        )

    loan_request = transaction.loan_requests[0]

    if not loan_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cannot find loan request for order",
        )
    loan_request_offers = loan_request.loan_offers

    if not loan_request_offers:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cannot find loan offers for order, wait until it come",
        )

    for offer in loan_request_offers:
        if offer.id == request.offer_id:
            loan_request.selected_offer = offer.id
            set_offer_response = await mfo_service.set_offer(
                pick_offer_data=PickOfferSchema(
                    reference_id=loan_request.mfo_uuid,
                    product=offer.outer_id,
                    credit_params=CreditParams(
                        period=offer.period, principal=offer.amount
                    ),
                )
            )
            if not set_offer_response.status_code == 200:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="MFO Set Offer ERROR, try again later",
                )

            db.add(loan_request)
            db.commit()
            db.refresh(loan_request)
            break
    return loan_request


@router.get("/customer/merchant-site", response_model=MerchantSiteSchema)
async def get_merchant_site(
    merchant_site: MerchantSite = Depends(get_merchant_site_from_site_domain),
):
    return merchant_site_controller.serialize_merchant_site(merchant_site)


@router.get("/customer/products", response_model=PaginatedProductsResponse)
async def get_products_by_merchant(
    first: Optional[int] = Query(
        30, description="Returns the first n elements from the list."
    ),
    last: Optional[int] = Query(
        None, description="Returns the last n elements from the list."
    ),
    after: Optional[str] = Query(
        None,
        description="Returns the elements in the list that come after the specified cursor.",
    ),
    before: Optional[str] = Query(
        None,
        description="Returns the elements in the list that come before the specified cursor.",
    ),
    merchant: Merchant = Depends(get_merchant_from_site_domain),
):
    where = ProductWhereInput(
        metadata=[
            {
                "key": "merchant_id",
                "value": merchant.id,
            }
        ]
    )
    products_response = await ss.client.list_products_with_all_filters(
        first=first, last=last, after=after, before=before, where=where
    )

    product_edges = products_response.products.edges

    processed_products = []
    for edge in product_edges:
        product_node = edge.node
        basic_variant = None
        if product_node.default_variant:
            first_variant = product_node.default_variant
            basic_variant = ProductVariantShortSchema(
                name=first_variant.name,
                id=first_variant.id,
                sku=first_variant.sku,
                price=(
                    first_variant.channel_listings[0].price.amount
                    if first_variant.channel_listings
                    else 0.0
                ),
                currency=(
                    first_variant.channel_listings[0].price.currency
                    if first_variant.channel_listings
                    else "KZT"
                ),
            )
        processed_products.append(
            ProductShortSchma(
                product_id=product_node.id,
                merchant_id=merchant.id,
                name=product_node.name,
                product_type_name=(
                    product_node.product_type.name
                    if product_node.product_type
                    else "Unknown"
                ),
                basic_variant=basic_variant,
                thumbnail_url=(
                    product_node.thumbnail.url if product_node.thumbnail else None
                ),
                thumbnail_alt=(
                    product_node.thumbnail.alt if product_node.thumbnail else None
                ),
                variants_count=product_node.product_variants.total_count,
            )
        )
    return PaginatedProductsResponse(
        total_count=products_response.products.total_count,
        has_next_page=products_response.products.page_info.has_next_page,
        has_previous_page=products_response.products.page_info.has_previous_page,
        items=processed_products,
    )


@router.get("/customer/products/{product_id}", response_model=ProductFullSchema)
async def get_product_by_merchant(
    product_id: str, merchant: Merchant = Depends(get_merchant_from_site_domain)
):
    pass


@router.get("/customer/variants", response_model=List[ProductVariantShortSchema])
async def get_variants_by_merchant(
    merchant: Merchant = Depends(get_merchant_from_site_domain),
):
    pass


@router.get("/customer/variants/{variant_id}", response_model=ProductVariantShortSchema)
async def get_variant_by_merchant(
    variant_id: str, merchant: Merchant = Depends(get_merchant_from_site_domain)
):
    pass


@router.get("/customer/category-trees", response_model=CategoryListSchema)
async def get_categories_by_merchant(
    merchant: Merchant = Depends(get_merchant_from_site_domain),
):
    pass


@router.post("/add-to-cart", response_model=CartSchema)
async def add_to_cart(
    request: CartLineOperationSchema,
    current_user: User = Depends(security.get_current_user),
):
    if not current_user.customer_profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User does not have a customer profile.",
        )

    customer_id = current_user.customer_profile.id

    correct_lines = [
        CheckoutLineInput(quantity=line.quantity, variant_id=line.variant_id)
        for line in request.lines
    ]

    # Get existing cart or create a new one
    cart_response = await ss.client.get_customer_checkouts_by_id(customer_id)

    if cart_response.checkouts.total_count > 0 and cart_response.checkouts.edges:
        # Assuming we want to use the first existing checkout if any
        existing_checkout = cart_response.checkouts.edges[0].node

        # Update the existing checkout with new lines
        update_checkout_response = await ss.client.add_lines_to_checkout(
            checkout_id=existing_checkout.id, lines=correct_lines
        )

        if not update_checkout_response.checkout_lines_add.errors:
            checkout = existing_checkout
        else:
            errors = (
                update_checkout_response.checkout_lines_add.errors
                if update_checkout_response.checkout_lines_add
                else "Unknown error"
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to update checkout lines: {errors}",
            )

        # If the update was successful, return the cart schema
        cart_items = []
        total_price = (
            checkout.total_price.gross.amount
            if checkout.total_price.gross.amount
            else 0.0
        )
        if checkout.lines:
            for line in checkout.lines:
                if line.variant:
                    item_price = (
                        line.variant.channel_listings[0].price.amount
                        if line.variant.channel_listings
                        else 0.0
                    )
                    cart_items.append(
                        CartItemSchema(
                            quantity=line.quantity,
                            variant_id=line.variant.id,
                            price=item_price,
                            product_name=line.variant.product.name,
                            variant_name=line.variant.name,
                        )
                    )
            return CartSchema(
                checkout_id=checkout.id, lines=cart_items, total_price=total_price
            )

    # else clean other checkouts

    # add channel slug
    channel_response = await ss.client.get_channel_by_id(
        settings.LINK_SALEOR_CHANNEL_ID
    )
    if not channel_response.channel or not channel_response.channel.slug:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not resolve Saleor channel.",
        )
    channel_slug = channel_response.channel.slug

    print(f"channel slug: {channel_slug}")
    print(f"customer id: {customer_id}")
    print(f"correct lines: {correct_lines}")

    create_checkout_response = await ss.client.create_checkout_for_customer(
        customer_id=customer_id, channel_slug=channel_slug, lines=correct_lines
    )

    if (
        create_checkout_response.checkout_create
        and create_checkout_response.checkout_create.checkout
    ):
        checkout = create_checkout_response.checkout_create.checkout
    else:
        errors = (
            create_checkout_response.checkout_create.errors
            if create_checkout_response.checkout_create
            else "Unknown error"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create or update checkout: {errors}",
        )

    # Process checkout lines into CartItemSchema
    cart_items = []
    total_price = (
        checkout.total_price.gross.amount if checkout.total_price.gross.amount else 0.0
    )
    if checkout.lines:
        for line in checkout.lines:
            if line.variant:
                item_price = line.variant.channel_listings[0].price.amount or 0.0
                cart_items.append(
                    CartItemSchema(
                        quantity=line.quantity,
                        variant_id=line.variant.id,
                        price=item_price,
                        product_name=line.variant.product.name,
                        variant_name=line.variant.name,
                    )
                )

    return CartSchema(
        checkout_id=checkout.id, lines=cart_items, total_price=total_price
    )


@router.delete("/remove-from-cart", response_model=CartSchema)
async def remove_from_cart(request: CartLineOperationSchema):
    """
    delete checkout item
    """
    pass


@router.get(
    "/cart", response_model=CartFullSchema
)  # Change to full according to information
async def get_cart(
    current_user: User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):

    if not current_user.customer_profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User does not have a customer profile.",
        )

    customer_id = current_user.customer_profile.id

    # Get the customer's checkout
    checkout_list_response = await ss.client.get_customer_checkouts_by_id(customer_id)

    if checkout_list_response.checkouts.total_count == 0:
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active cart found for the customer.",
        )

    checkout = checkout_list_response.checkouts.edges[0].node
    saleor_checkout_id = checkout.id

    full_checkout_response = await ss.client.get_full_checkout_by_id(saleor_checkout_id)

    unique_mechant_ids = set()

    for item in full_checkout_response.checkout.lines:
        if item.variant.product.metafields.get("merchant_id"):
            unique_mechant_ids.add(item.variant.product.metafields["merchant_id"])

    if len(unique_mechant_ids) > 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Checkout contains items from multiple merchants.",
        )

    items = []
    for line in full_checkout_response.checkout.lines:
        items.append(
            CartItemSchema(
                quantity=line.quantity,
                variant_id=line.variant.id,
                price=(
                    line.variant.channel_listings[0].price.amount
                    if line.variant.channel_listings
                    else 0.0
                ),
                product_name=line.variant.product.name,
                variant_name=line.variant.name,
            )
        )

    total_price = full_checkout_response.checkout.total_price.gross.amount

    shipping_address = full_checkout_response.checkout.shipping_address
    shipping_methods = full_checkout_response.checkout.available_shipping_methods
    shipping_methods_list = [
        ShippingMethodSchema(
            id=method.id,
            name=method.name,
            price=method.price.amount if method.price.amount else 0.0,
        )
        for method in shipping_methods
    ]

    shiping_method = full_checkout_response.checkout.shipping_method

    collection_points = full_checkout_response.checkout.available_collection_points

    collection_points_list = [
        CollectionPointSchema(
            id=point.id,
            name=point.name,
            address=CartAddressSchema(
                street_address1=point.address.street_address_1,
                street_address2=point.address.street_address_2,
                city=point.address.city,
                country=point.address.country.country,
            ),
        )
        for point in collection_points
    ]

    merchant = get_merchant_by_id(db=db, merchant_id=unique_mechant_ids.pop())

    types = [
        (method.base_method.type)
        for method in merchant.merchant_payment_methods
        if method.active
    ]

    types = set(types)

    order_readiness = False

    if (
        full_checkout_response.checkout.shipping_address
        and full_checkout_response.checkout.shipping_method
    ):
        order_readiness = True

    response = CartFullSchema(
        checkout_id=saleor_checkout_id,
        items=items,
        total_price=total_price,
        shipping_address=CartAddressSchema(
            street_address1=shipping_address.street_address_1,
            street_address2=shipping_address.street_address_2,
            city=shipping_address.city,
            country=shipping_address.country.country,
        ),
        shipping_methods=shipping_methods_list,
        available_payment_methods=types,
        collection_points=collection_points_list,
        selected_shipping_method=shiping_method.name if shiping_method else None,
        ready_to_order=order_readiness,
    )

    return response


@router.patch(
    "/cart", response_model=CartFullSchema
)  # Change to full according to information
async def update_cart(
    request: CartFullPatchShema,
    current_user: User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.customer_profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User does not have a customer profile.",
        )

    customer_id = current_user.customer_profile.id

    # Get the customer's checkout
    checkout_list_response = await ss.client.get_customer_checkouts_by_id(customer_id)

    if checkout_list_response.checkouts.total_count == 0:
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active cart found for the customer.",
        )

    checkout = checkout_list_response.checkouts.edges[0].node
    saleor_checkout_id = checkout.id

    if request.shipping_address:
        # process shipping address
        update_address_response = await ss.client.update_checkout_addresses(
            checkout_id=saleor_checkout_id,
            country="KZ",
            city=request.shipping_address.city,
            street_1=request.shipping_address.street_address1,
            street_2=request.shipping_address.street_address2,
            validate=False,
            phone=current_user.phone_number,
        )

        if update_address_response.checkout_billing_address_update.errors:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to update checkout address.",
            )
        if update_address_response.checkout_shipping_address_update.errors:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to update checkout address.",
            )

    if request.shipping_method:
        # process shipping methods
        update_shipping_method_response = (
            await ss.client.set_shipping_method_for_checkout(
                shipping_method=request.shipping_method, checkout_id=saleor_checkout_id
            )
        )

        if update_shipping_method_response.checkout_shipping_method_update.errors:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to update shipping_address",
            )
    if request.my_address_id:
        customer = current_user.customer_profile
        customer_addresses = customer.delivery_addresses
        print(customer_addresses)
        for address in customer_addresses:
            if address.id == request.my_address_id:
                update_checkout_response = await ss.client.update_checkout_addresses(
                    checkout_id=saleor_checkout_id,
                    country="KZ",  # todo fix to normal
                    city=address.city.name["ru"],
                    street_1=address.address_line_1,
                    street_2=address.address_line_2,
                    validate=False,
                    phone=current_user.phone_number,
                )

                if update_checkout_response.checkout_billing_address_update.errors:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Failed to update shipping_address by id",
                    )
                break

    full_checkout_response = await ss.client.get_full_checkout_by_id(saleor_checkout_id)

    unique_mechant_ids = set()

    for item in full_checkout_response.checkout.lines:
        if item.variant.product.metafields.get("merchant_id"):
            unique_mechant_ids.add(item.variant.product.metafields["merchant_id"])

    if len(unique_mechant_ids) > 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Checkout contains items from multiple merchants.",
        )
    items = []
    for line in full_checkout_response.checkout.lines:
        items.append(
            CartItemSchema(
                quantity=line.quantity,
                variant_id=line.variant.id,
                price=(
                    line.variant.channel_listings[0].price.amount
                    if line.variant.channel_listings
                    else 0.0
                ),
                product_name=line.variant.product.name,
                variant_name=line.variant.name,
            )
        )

    total_price = full_checkout_response.checkout.total_price.gross.amount

    shipping_address = full_checkout_response.checkout.shipping_address
    shipping_methods = full_checkout_response.checkout.available_shipping_methods
    shipping_methods_list = [
        ShippingMethodSchema(
            id=method.id,
            name=method.name,
            price=method.price.amount if method.price.amount else 0.0,
        )
        for method in shipping_methods
    ]

    shiping_method = full_checkout_response.checkout.shipping_method

    collection_points = full_checkout_response.checkout.available_collection_points

    collection_points_list = [
        CollectionPointSchema(
            id=point.id,
            name=point.name,
            address=CartAddressSchema(
                street_address1=point.address.street_address_1,
                street_address2=point.address.street_address_2,
                city=point.address.city,
                country=point.address.country.country,
            ),
        )
        for point in collection_points
    ]

    merchant = get_merchant_by_id(db=db, merchant_id=unique_mechant_ids.pop())

    types = [
        (method.base_method.type)
        for method in merchant.merchant_payment_methods
        if method.active
    ]

    types = set(types)

    order_readiness = False

    if (
        full_checkout_response.checkout.shipping_address
        and full_checkout_response.checkout.shipping_method
    ):
        order_readiness = True

    response = CartFullSchema(
        checkout_id=saleor_checkout_id,
        items=items,
        total_price=total_price,
        shipping_address=CartAddressSchema(
            street_address1=shipping_address.street_address_1,
            street_address2=shipping_address.street_address_2,
            city=shipping_address.city,
            country=shipping_address.country.country,
        ),
        shipping_methods=shipping_methods_list,
        available_payment_methods=types,
        collection_points=collection_points_list,
        selected_shipping_method=shiping_method.name if shiping_method else None,
        ready_to_order=order_readiness,
    )

    return response


@router.post("/cart/complete-and-order", response_model=CreateOrderResponse)
async def cart_complete_and_order(
    request: CompleteCheckoutRequestSchema,
    current_user: User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.customer_profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User does not have a customer profile.",
        )

    customer_id = current_user.customer_profile.id

    # Get the customer's checkout
    cart_response = await ss.client.get_customer_checkouts_by_id(customer_id)

    if (
        not cart_response.checkouts.total_count > 0
        and not cart_response.checkouts.edges
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active cart found for the customer.",
        )

    # Assuming we want to use the first existing checkout if any
    existing_checkout = cart_response.checkouts.edges[0].node
    saleor_checkout_id = existing_checkout.id

    product_request = await ss.client.get_product(
        existing_checkout.lines[0].variant.product.id
    )

    merchant_id = product_request.product.metafields["merchant_id"]

    if not existing_checkout.email:
        email = f"user-{current_user.id}@airshop.saleor.local"

        update_checkout_response = await ss.client.update_checkout_email(
            checkout_id=saleor_checkout_id, email=email
        )

        if update_checkout_response.checkout_email_update.errors:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update checkout email.",
            )

    # Create order from the checkout
    try:
        order_response = await ss.client.create_order_from_saleor_checkout(
            checkout_id=saleor_checkout_id, merchant_id=merchant_id
        )

        order_create_result = order_response.order_create_from_checkout
        if order_create_result.errors:
            error_messages = [
                e.message for e in order_create_result.errors if e.message
            ]
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Could not create order from checkout in Saleor: {'; '.join(error_messages)}",
            )

        if not order_create_result.order or not order_create_result.order.id:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Saleor created an order but did not return an ID.",
            )

        saleor_order_id = order_create_result.order.id
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during Saleor order creation: {e}",
        )

    # 6. Create internal transaction record (acting as our 'order')
    new_transaction = transactions_controller.create_transaction(
        db=db,
        saleor_order_id=saleor_order_id,
        amount=existing_checkout.total_price.gross.amount,
    )

    # 7. Return the ID of our internal transaction/order
    return {"order_id": saleor_order_id}


@router.delete("/cart", response_model=CartSchema)
async def delete_cart():
    """
    delete all checkout items

    """
    pass


@router.get("/city-list", response_model=CursorPageWithOutTotal[CityModelSchema])
async def get_city_list(
    merchant: Merchant = Depends(get_merchant_from_site_domain),
    params: CursorParamsWithOutTotal = Depends(),
):
    # return paginate(db, query, params)
    pass


@router.get("/customer/search", response_model=PaginatedProductsResponse)
async def search_products(merchant: Merchant = Depends(get_merchant_from_site_domain)):
    pass


@router.get("/countries", response_model=CursorPageWithOutTotal[CountryModelSchema])
async def get_countries(
    db: Session = Depends(get_db),
    params: CursorParamsWithOutTotal = Depends(),
):
    query = country_controller.get_cursor_query(db=db)
    return paginate(db, query, params)


@router.get("/cities", response_model=CursorPageWithOutTotal[CityModelSchema])
async def get_cities(
    db: Session = Depends(get_db),
    params: CursorParamsWithOutTotal = Depends(),
):
    query = city_controller.get_cursor_query(db=db)
    return paginate(db, query, params)


@router.get(
    "/my-addresses", response_model=CursorPageWithOutTotal[AddressListModelSchema]
)
async def list_customer_address(
    current_user: User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
    params: CursorParamsWithOutTotal = Depends(),
):
    query = address_controller.get_all_addresses_by_user_id(
        db=db, user_id=current_user.id, as_query=True
    )
    query = address_controller.get_cursor_query(db, base_query=query)
    return paginate(db, query, params)


@router.post("/my-addresses", response_model=AddressModelSchema)
async def create_customer_address(
    request: AddressCustomerInputSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(security.get_current_user),
):
    if not current_user.customer_profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User does not have a customer profile.",
        )

    customer_id = current_user.customer_profile.id

    # Create the address and link it to the customer
    new_address = customer_controller.create_delivery_address(
        db=db, customer_id=customer_id, address=request
    )

    return AddressModelSchema(
        id=new_address.id,
        name=new_address.name,
        address_line_1=new_address.address_line_1,
        address_line_2=new_address.address_line_2,
        address_line_3=new_address.address_line_3,
        country=CountryModelSchema(
            id=new_address.country.id,
            name=new_address.country.name,
            currency_code=new_address.country.currency_code,
            postal_codes_range=new_address.country.postal_codes_range[0],
        ),
        city=CityModelSchema(
            id=new_address.city.id,
            name=new_address.city.name,
            country_id=new_address.city.country_id,
            country=CountryModelSchema(
                id=new_address.city.country.id,
                name=new_address.city.country.name,
                currency_code=new_address.city.country.currency_code,
                postal_codes_range=new_address.city.country.postal_codes_range[0],
            ),
        ),
    )


@router.get("/my-addresses/{address_id}", response_model=AddressModelSchema)
async def get_customer_address(
    address_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(security.get_current_user),
):
    if not current_user.customer_profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User does not have a customer profile.",
        )

    customer_id = current_user.customer_profile.id

    address = customer_controller.get_address_by_id(
        db=db, address_id=address_id, customer_id=customer_id
    )

    if not address:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Address not found.",
        )

    return AddressModelSchema(
        id=address.id,
        name=address.name,
        address_line_1=address.address_line_1,
        address_line_2=address.address_line_2,
        address_line_3=address.address_line_3,
        country=CountryModelSchema(
            id=address.country.id,
            name=address.country.name,
            currency_code=address.country.currency_code,
            postal_codes_range=address.country.postal_codes_range[0],
        ),
        city=CityModelSchema(
            id=address.city.id,
            name=address.city.name,
            country_id=address.city.country_id,
            country=CountryModelSchema(
                id=address.city.country.id,
                name=address.city.country.name,
                currency_code=address.city.country.currency_code,
                postal_codes_range=address.city.country.postal_codes_range[0],
            ),
        ),
    )


@router.patch("/my-addresses/{address_id}")
async def update_customer_address():
    pass


@router.delete("/my-addresses/{address_id}")
async def delete_customer_address():
    # TODO: Implement soft delete of customer address
    pass


# Messages for customer????
