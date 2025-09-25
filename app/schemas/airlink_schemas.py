# app/schemas/airlink_schemas.py

from datetime import datetime
from decimal import Decimal
from typing import Optional, List

from pydantic import BaseModel, HttpUrl, Field


# A simple Pydantic model for a product variant
class QuickAirlinkRequest(BaseModel):
    """
    Schema for a request to quickly create an Airlink.
    """

    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None


class QuickAirlinkResponse(BaseModel):
    airlink_id: str
    status: str


class AirlinkImages(BaseModel):
    """
    Schema for Airlink images.
    """

    url: Optional[HttpUrl]
    is_main: bool = False


class AirlinkProductVariantSchema(BaseModel):
    """
    Schema for an Airlink product variant.
    """

    variant_id: str
    name: str
    price: Decimal
    currency: str
    stock_quantity: int


class AirlinkProductSchema(BaseModel):
    """
    Schema for an Airlink product.
    """

    name: str
    description: Optional[str] = None
    variants: List[AirlinkProductVariantSchema]
    images: List[AirlinkImages] = []


class AirlinkCreateRequest(BaseModel):
    """
    Schema for creating a detailed Airlink.
    """

    name: Optional[str] = None
    description: Optional[str] = None
    date_start: datetime
    date_end: datetime
    products: Optional[List[AirlinkProductSchema]] = []
    merchant_id: str
    images: Optional[List[AirlinkImages]] = None
    planned_price: Optional[Decimal] = None


class AirlinkUpdateRequest(BaseModel):
    """
    Schema for updating an existing Airlink.
    All fields are optional, allowing for partial updates.
    """

    name: Optional[str] = None
    description: Optional[str] = None
    date_start: Optional[datetime] = None
    date_end: Optional[datetime] = None
    products: Optional[List[AirlinkProductSchema]] = None
    images: Optional[List[AirlinkImages]] = None
    published: Optional[bool] = None
    public_url: Optional[str] = None
    planned_price: Optional[Decimal] = None


class AirlinkPublishRequest(BaseModel):
    """
    Schema for publishing an Airlink.
    """

    published: str


class AirlinkStatusUpdate(BaseModel):
    """
    Schema for updating the status of an Airlink.
    """

    status: str


class AirlinkProductVariantUpdateSchema(BaseModel):
    """
    Schema for updating an Airlink product variant.
    """

    variant_id: str
    name: Optional[str] = None
    price: Optional[Decimal] = None
    currency: Optional[str] = None
    stock_quantity: Optional[int] = None


class AirlinkProductUpdateSchema(BaseModel):
    """
    Schema for updating an Airlink product.
    """

    product_id: str
    name: Optional[str] = None
    description: Optional[str] = None
    variants: Optional[List[AirlinkProductVariantUpdateSchema]] = None
    images: Optional[List[AirlinkImages]] = None


class AirlinkImageUploadRequest(BaseModel):
    """
    Schema for requesting an image upload URL for an Airlink.
    """

    filename: str
    content_type: str


class AirlinkImageUploadResponse(BaseModel):
    """
    Schema for the response containing the image upload URL.
    """

    upload_url: HttpUrl
    filename: str


class AirlinkResponseSchema(BaseModel):
    """
    Schema for an Airlink.
    """

    uuid: str = Field(..., alias="id")
    moderation_status: str
    name: Optional[str] = None
    description: Optional[str] = None
    date_start: datetime
    date_end: datetime
    merchant_id: str
    created_at: datetime
    updated_at: datetime
    total_price: Optional[Decimal] = None
    planned_price: Optional[Decimal] = None
    images: List[AirlinkImages] = []
    published: bool = False
    public_url: Optional[str] = None


class QuickAirlinkStatus(BaseModel):
    """
    Schema for the status of a quick Airlink.
    """

    airlink_id: str
    status: str
    preview: Optional[AirlinkResponseSchema] = None  # TODO: REMOVE LIST


class AirlinkPatchRequestRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    date_start: Optional[datetime] = None
    date_end: Optional[datetime] = None
    price: Optional[Decimal] = None


class CreateOrderByAirlinkAndPhoneNumberPayload(BaseModel):
    phone_number: str = Field(
        ...,
        min_length=10,
        max_length=15,
        description="The user's phone number.",
        examples=["+1234567890"],
    )
    airlink_id: str


class CreateOrderByAirlinkAndPhoneNumberResponse(BaseModel):
    code: int
    message: str
    order_id: str | None = None
