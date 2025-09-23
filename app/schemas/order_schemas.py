# full methods:
# GET order by airlink / airlink id - information public method -retrievs information about airlink, payment options
# POST order by airlink/ airlink id - authorized customer only
# PATCH order by airlink / - airlink_id - change payment type
# order by airlink / process-payment -
# order by airlink / process-payment - set iin
# order by airlink / process-payment / get-offers
# order by airlink / process-payment / offer post
# order by airlink / process-payment / offer patch
from prompt_toolkit.contrib.regular_languages.regex_parser import AnyNode
from pydantic import BaseModel, HttpUrl
from typing import Optional, Any, List
from app.schemas.airlink_schemas import AirlinkResponseSchema
from app.schemas.integrations import MerchantOnboardResponse
from app.graphql.generated_client.get_order_by_id import GetOrderByIDOrder
from app.schemas.customer_schemas import CustomerBaseSchema
from app.schemas.integrations import MerchantOnboardRequest
from app.schemas.basic_schemas import PaginatedResponse


class BasePaymentMethodSchema(BaseModel):
    id: str
    type: str
    loan_type: Optional[str] = None
    loan_period_range: Optional[str] = None  # Representing INT4RANGE as string for now
    enabled: bool


class MerchantPaymentMethodSchema(BaseModel):
    id: str
    merchant: MerchantOnboardResponse = None  # Nested merchant details
    active: bool
    base_method: Optional[BasePaymentMethodSchema] = None  # Nested base method details


class OrderByAirlinkResponse(BaseModel):
    """
    Schema represents get order by airlink response
    Containts airlink model
    and merchant available payment option
    GET order by airlink / airlink id
    """

    airlink: AirlinkResponseSchema
    merchant: MerchantOnboardResponse
    availablePaymentOptions: list[MerchantPaymentMethodSchema]


class CreateOrderByAirlinkRequest(BaseModel):
    """
    Schema for creating an order from an Airlink.
    POST order by airlink/ airlink id - authorized customer only
    PATCH order by airlink / - airlink_id - change payment type
    """

    payment_method_id: str


class SetIINRequest(BaseModel):
    """Sets IIN for loan request
    # order by airlink / process-payment - set iin
    """

    iin: str


class OfferSchema(BaseModel):
    """
    offers schema
    helps to list offers
    """

    id: str
    loan_type: str
    loan_period: int
    amount: float


class LoanOffersResponse(BaseModel):
    """
    loan offers response
    # order by airlink / process-payment / get-offers
    """

    offers: list[OfferSchema]


class SetOfferRequest:
    """
    set offer request
    # order by airlink / process-payment / offer post
    # order by airlink / process-payment / offer patch
    """

    offer_id: str


class CreateOrderResponse(BaseModel):
    """
    Response schema after creating an order from an Airlink.
    """

    order_id: str


class OrderProcessPaymentResponse(BaseModel):
    status: str
    required_action: Optional[str] = None
    redirect_url: Optional[HttpUrl] = None


class SaleorOrderSchema(BaseModel):
    order: Any
    customer: CustomerBaseSchema
    merchant: MerchantOnboardRequest


class SaleorOrdersListSchema(BaseModel):
    orders: list[SaleorOrderSchema]


class MerchantPaymentMethodPaginatedResponse(PaginatedResponse):
    items: list[MerchantPaymentMethodSchema]
