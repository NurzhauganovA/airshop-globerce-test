from typing import Optional

from pydantic import BaseModel, field_validator
from app.controllers.internal import address_controller
from app.models.internal_model import Address
from sqlalchemy.orm import Session

class CountryModelSchema(BaseModel):
    id: str
    name: dict
    currency_code: str
    postal_codes_range: dict | None = None

    @field_validator("postal_codes_range", mode="before")
    @classmethod
    def pick_first_postal_range(cls, value):
        if isinstance(value, list):
            if not value:
                return None
            first = value[0]
            if isinstance(first, dict):
                return first
            raise TypeError("postal_codes_range list must contain dictionaries")
        return value


class CityModelSchema(BaseModel):
    id: str
    name: dict
    country_id: str
    country: CountryModelSchema


class AddressModelSchema(BaseModel):
    id: str
    name: str
    contact_phone: Optional[str] = None
    address_line_1: str
    address_line_2: Optional[str] = None
    address_line_3: Optional[str] = None
    country: CountryModelSchema
    city: CityModelSchema


class AddressCustomerInputSchema(BaseModel):
    name: str
    address_line_1: str
    address_line_2: Optional[str] = None
    address_line_3: Optional[str] = None
    contact_phone: Optional[str] = None
    country_id: Optional[str] = None
    city_id: str

    def to_db_model(self) -> Address:
        return Address(
            name=self.name,
            contact_phone=self.contact_phone,
            address_line_1=self.address_line_1,
            address_line_2=self.address_line_2,
            address_line_3=self.address_line_3,
            country_id=self.country_id if self.country_id else None,
            city_id=self.city_id,
        )
    
    @staticmethod
    def from_db_model(db_model: Address):
        return AddressCustomerInputSchema(
            name=db_model.name in db_model,
            address_line_1=db_model.address_line_1,
            address_line_2=db_model.address_line_2,
            address_line_3=db_model.address_line_3,
            contact_phone=db_model.contact_phone,
            country_id=db_model.country_id,
            city_id=db_model.city_id,
        )
    
    def update_db_model(self, db_model: Address):
        db_model.name = self.name
        db_model.address_line_1 = self.address_line_1
        db_model.address_line_2 = self.address_line_2
        db_model.address_line_3 = self.address_line_3
        db_model.contact_phone = self.contact_phone
        db_model.country_id = self.country_id
        db_model.city_id = self.city_id
        return db_model
    
    @staticmethod
    def load_address_by_id(db: Session, address_id: str) -> Optional["AddressCustomerInputSchema"]:
        db_address = address_controller.get_address_by_id(db, address_id=address_id)
        if db_address:
            return AddressCustomerInputSchema.from_db_model(db_address)



class AddressListModelSchema(BaseModel):
    id: str
    name: str
    address_line_1: str
    address_line_2: Optional[str] = None
    address_line_3: Optional[str] = None
    contact_phone: Optional[str] = None
