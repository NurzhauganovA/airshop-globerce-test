from pydantic import BaseModel
from typing import List, Optional
from app.schemas.basic_schemas import PaginatedResponse


class MerchantCategorySchema(BaseModel):
    id: str
    saleor_category_id: str
    merchant_id: str


class CategorySchema(BaseModel):
    id: str
    name: Optional[str] = None
    description: Optional[str] = None
    seoTitle: Optional[str] = None
    seoDescription: Optional[str] = None
    slug: str
    parent: Optional["CategorySchema"] = None
    level: int
    children: List["CategorySchema"] = []


class CategoryListSchema(PaginatedResponse):
    items: List[CategorySchema]
