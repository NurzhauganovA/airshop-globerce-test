from pydantic import BaseModel
from typing import Optional


class LoanOfferModelSchema(BaseModel):
    """
    model for loan offer
    """

    id: str
    loan_request_id: str
    loan_type: str
    period: int
    amount: float
    suitable: bool


class LoanRequestModelSchema(BaseModel):
    """
    model LoanRequest
    """

    id: str
    transaction_id: str
    redirect_url: str
    fallback_url: str
    status_url: str
    status: str
    iin: str
    offers: Optional[list[LoanOfferModelSchema]] = None
    selected_offer: Optional[LoanOfferModelSchema] = None


class GetOffersResponse(BaseModel):
    """
    model for get offers request
    """

    offers: list[LoanOfferModelSchema]
    status: str
    redirect_url: Optional[str]


class SetOfferRequest(BaseModel):
    """
    model for pick offer request
    """

    offer_id: str


class CreditParamsSchema(BaseModel):
    """
    model for credit params
    will be used to send request to MFO
    """

    principal: float
    period: int


class AdditionalInformationMFOSchema(BaseModel):
    """
    Schema for additional information for MFO
    """

    reference_id: str
    success_url: str
    failure_url: str
    seller_phone: str


class MerchantInfoMFOSchema(BaseModel):
    """
    Schema for merchant information for MFO
    """

    bin: str
    name: str


class CreditGoodsMFOSchema(BaseModel):
    """
    Schema for credit goods for MFO
    """

    name: str
    quantity: int
    price: float


class MFOApplyLeadSchema(BaseModel):
    """
    Schema for MFO apply lead request
    """

    iin: str
    mobile_phone: str
    product: str
    partner: str
    channel: str
    credit_params: CreditParamsSchema
    additional_information: AdditionalInformationMFOSchema
    merchant_info: MerchantInfoMFOSchema
    credit_goods: list[CreditGoodsMFOSchema]


class MFOHookOfferSchema(BaseModel):
    principal: float
    period: int
    loan_type: str
    monthly_payment: float


class MFOHookCustomerSchema(BaseModel):
    first_name: str
    last_name: str
    middle_name: str


class MFOHookSchema(BaseModel):
    status: str
    customer: Optional[MFOHookCustomerSchema] = None
    offers: Optional[list[MFOHookOfferSchema]] = None


class MFOHookResponseSchema(BaseModel):
    reference_id: str
    status: str


class LoanRequestCreateSchema(BaseModel):
    """
    model for create loan request
    """

    transaction_id: str
    status: str | None = "PENDING"
    iin: str


class LoanRequestUpdateSchema(BaseModel):
    """
    model for update loan request
    """

    transaction_id: str | None = None
    redirect_url: str | None = None
    fallback_url: str | None = None
    status_url: str | None = None
    status: str | None = None
    iin: str | None = None
    selected_offer: str | None = None


class LoanOfferCreateSchema(BaseModel):
    """
    model for create loan offer
    """

    loan_request_id: str
    loan_type: str
    period: int
    amount: float
    suitable: bool = False
    outer_id: Optional[str] = None


class LoanOfferUpdateSchema(BaseModel):
    """
    model for update loan offer
    """

    loan_type: str | None = None
    period: int | None = None
    amount: float | None = None
    suitable: bool | None = None
