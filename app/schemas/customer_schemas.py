# app/schemas/customer_schemas.py

from pydantic import BaseModel
from typing import List, Optional

from app.models.internal_model import Customer


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

    @staticmethod
    def from_db_model(customer: Customer) -> "CustomerBaseSchema":
        """
        Create a CustomerBaseSchema from a Customer ORM model.
        """
        return CustomerBaseSchema(
            id=customer.id,
            first_name=customer.first_name,
            last_name=customer.surname,
            email=customer.user.email if customer.user else None,
            phone_number=customer.user.phone_number if customer.user else None,
        )
