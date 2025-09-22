from pydantic import BaseModel
from typing import Optional, Any, List
from app.schemas.basic_schemas import PaginatedResponse


class CreateProductRequestSchema(BaseModel):
    name: str
    category_id: str
    sku: Optional[str] = None
    price: float


class CreateProductResponseSchema(BaseModel):
    """
    create product reponse
    """

    product_id: str
    product_name: str
    product_slug: str
    variant_id: str
    merchant_id: str


class ProductVariantShortSchema(BaseModel):
    name: str
    id: str
    sku: Optional[str] = None
    price: float
    currency: str


class ProductFullSchema(BaseModel):
    product_id: str
    merchant_id: str
    name: str
    product_type_name: str
    basic_variant: Optional[ProductVariantShortSchema] = None
    thumbnail_url: str
    thumbnail_alt: str
    variants_count: int
    media: Optional[Any] = None
    images: Optional[Any] = None
    variants: List[ProductVariantShortSchema]
    attributes: List[Any]


class ProductShortSchma(BaseModel):
    product_id: str
    merchant_id: str
    name: str
    product_type_name: str
    basic_variant: Optional[ProductVariantShortSchema] = None
    thumbnail_url: Optional[str] = None
    thumbnail_alt: Optional[str] = None
    variants_count: int


class PaginatedProductsResponse(PaginatedResponse):
    items: List[ProductShortSchma]
