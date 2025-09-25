from pydantic import BaseModel
from typing import Optional, List, Any
from pydantic.types import UUID
from app.schemas.basic_schemas import PaginatedResponse
from app.schemas.address_schema import AddressCustomerInputSchema


class WarehouseSchema(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    slug: Optional[str] = None


class MerchantWarehouseSchema(BaseModel):
    id: str
    saleor_warehouse_id: str
    merchant_id: str
    warehouse: Optional[WarehouseSchema] = None
    address: Optional[AddressCustomerInputSchema] = None




class PaginatedMerchantWarehousesResponse(PaginatedResponse):
    total_count: int
    has_next_page: bool
    has_previous_page: bool
    items: List[MerchantWarehouseSchema]


class ShippingZoneSchema(BaseModel):
    id: UUID
    name: str
    saleor_shipping_zone_id: str
    warehouses: Optional[List[WarehouseSchema]] = []
    shipping_methods: Optional[List[Any]] = []


class CreateShippingZoneRequest(BaseModel):
    name: str


class ShippingZonesModelListSchema(PaginatedResponse):
    items: list[ShippingZoneSchema]


class PatchListMerchantWarehousesSchema(BaseModel):
    warehouses: List[str]


class PatchShippingZoneRequest(BaseModel):
    name: str
    warehouses: Optional[List[str]] = []


class CreateMerchantWarehouseSchema(WarehouseSchema):
    name: str
    address: AddressCustomerInputSchema


class PatchMerchantWarehouseSchema(CreateMerchantWarehouseSchema):
    name: Optional[str] = None
    address: Optional[AddressCustomerInputSchema] = None


class AddShippingMethodToShippingZoneRequest(BaseModel):
    name: str
    price: int
    maximum_order_price: Optional[int] = None
    minimum_order_price: Optional[int] = None
    maximum_delivery_days: Optional[int] = None
    minimum_delivery_days: Optional[int] = None


class ShippingMethodPriceSchema(BaseModel):
    channel_id: Optional[str] = None
    channel_name: Optional[str] = None
    price: Optional[float] = None
    maximum_order_price: Optional[float] = None
    minimum_order_price: Optional[float] = None


class ShippingMethodSchema(BaseModel):
    shipping_id: Optional[str] = None
    name: Optional[str] = None
    minimum_delivery_days: Optional[int] = None
    maximum_delivery_days: Optional[int] = None
    pricing_by_channels: Optional[List[ShippingMethodPriceSchema]] = []


class FullShippingZoneSchema(ShippingZoneSchema):
    shipping_methods: Optional[List[ShippingMethodSchema]] = []


class CreateProductStockSchema(BaseModel):
    product_variant_id: str
    quantity: int
