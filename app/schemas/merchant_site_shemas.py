from pydantic import BaseModel
from pydantic.types import UUID
from typing import Optional


class MerchantSiteCarouselItemSchema(BaseModel):
    id: str
    url: str
    is_active: bool
    order: int


class MerchantSiteSchema(BaseModel):
    id: UUID
    site_preffix: str
    site_suffix: Optional[str] = None
    is_active: bool
    site_carousel_items: list[MerchantSiteCarouselItemSchema] = []


class MerchantSiteCreateSchema(BaseModel):
    site_preffix: str
    site_suffix: Optional[str] = None
    is_active: bool = True


class MerchantSiteUpdateSchema(BaseModel):
    site_preffix: Optional[str] = None
    site_suffix: Optional[str] = None
    is_active: Optional[bool] = None


class MerchantSiteCarouselItemCreateSchema(BaseModel):
    url: str
    is_active: bool = True
    order: int


class MerchantSiteCarouselItemUpdateSchema(BaseModel):
    url: Optional[str] = None
    is_active: Optional[bool] = None
    order: Optional[int] = None
