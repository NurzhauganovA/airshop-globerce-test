from pydantic import BaseModel
from typing import List, Optional


class CartItemSchema(BaseModel):
    quantity: int
    variant_id: str
    price: Optional[int] = None
    product_name: Optional[str] = None
    variant_name: Optional[str] = None


class CartSchema(BaseModel):
    checkout_id: str
    lines: List[CartItemSchema] = []
    total_price: float


class CartLineOperationSchema(BaseModel):
    lines: List[CartItemSchema]


class ShippingAddressSchema(BaseModel):
    street_address1: str
    street_address2: Optional[str] = None
    city: str
    country: str


class ShippingMethodSchema(BaseModel):
    id: str
    name: str
    price: float


class CartAddressSchema(BaseModel):
    street_address1: str
    street_address2: str
    city: str
    country: str


class CollectionPointSchema(BaseModel):
    id: str
    name: str
    address: Optional[CartAddressSchema] = (
        None  # You might want to define a more specific AddressSchema
    )


class CartFullSchema(BaseModel):
    checkout_id: str
    items: List[CartItemSchema]
    total_price: float
    shipping_address: Optional[CartAddressSchema] = (
        None  # Define a proper AddressSchema if needed
    )
    shipping_methods: List[
        ShippingMethodSchema
    ]  # Define a proper ShippingMethodSchema if needed
    available_payment_methods: List[str]
    collection_points: List[CollectionPointSchema]
    selected_shipping_method: Optional[str] = None
    ready_to_order: bool = False


class CartFullPatchShema(BaseModel):
    shipping_address: Optional[CartAddressSchema] = None
    shipping_method: Optional[str] = None
    my_address_id: Optional[str] = None


class CompleteCheckoutRequestSchema(BaseModel):
    shipping_method: str
