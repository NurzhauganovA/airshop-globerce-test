# app/schemas/customer_schemas.py

from pydantic import BaseModel
from typing import List, Optional


# A simple Pydantic model for a product variant
class ProductVariantSchema(BaseModel):
    """
    Schema for a product variant as seen by a customer.
    """

    id: str
    name: str
    sku: Optional[str] = None
    price: float
    currency: str
    stock_quantity: int


# Schema for a full product
class ProductSchema(BaseModel):
    """
    Schema for a product as seen by a customer.
    """

    id: str
    name: str
    slug: str
    seo_title: Optional[str] = None  # New field
    seo_description: Optional[str] = None  # New field
    description: Optional[str] = None
    variants: List[ProductVariantSchema]


# A simple Pydantic model for a category
class CategorySchema(BaseModel):
    """
    Schema for a product category.
    """

    id: str
    name: str
    slug: str


class CustomerBaseSchema(BaseModel):
    id: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone_number: Optional[str] = None
