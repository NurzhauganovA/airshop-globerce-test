from __future__ import annotations

from typing import Optional


from pydantic import BaseModel, Field, field_serializer
from pydantic.types import datetime
from app.models.internal_model import Merchant
from datetime import timezone


class MerchantAddressCreate(BaseModel):
    name: str
    contact_phone: Optional[str] = None
    address_line_1: str
    address_line_2: Optional[str] = None
    address_line_3: Optional[str] = None
    country_id: str
    city_id: str
    type: str = Field(..., pattern="^(PRIMARY|WAREHOUSE)$")

class MerchantOnboardRequestEmployee(BaseModel):
    first_name: str = Field(..., min_length=2, max_length=50)
    middle_name: str = Field(..., min_length=2, max_length=50)
    last_name: str = Field(..., min_length=2, max_length=50)
    profile_id: str = Field(..., min_length=2, max_length=50)
    external_id: str = Field(..., min_length=2, max_length=50)

class MerchantOnboardResponse(BaseModel):
    status: str
    merchant_id: str
    message: str

class MerchantOnboardRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=50)
    bin: str = Field(..., min_length=12, max_length=12)
    bank_account: str = Field(..., min_length=5, max_length=40)
    phone: str = Field(..., min_length=5, max_length=40)
    company_id: str = Field(..., min_length=5, max_length=40)
    company_type: str = Field(..., pattern="^(LLC|IP)$")
    registration_date: str = Field(..., min_length=5, max_length=40)
    employee: MerchantOnboardRequestEmployee

    def to_db_model(self) -> Merchant:
        """returns db model to saving"""
        return Merchant(
            legal_name=self.name,
            bin=self.bin,
            iban=self.bank_account,
            phone=self.phone,
            company_id=self.company_id,
            company_type=self.company_type,
            registration_date=self.model_dump()["registration_date"],
        )
    
    @field_serializer("registration_date")
    def serialize_registration_date(self, registration_date: str) -> datetime:
        try:
            date_naive = datetime.fromisoformat(registration_date)
            return date_naive.replace(tzinfo=None)
        except Exception as e:
            raise ValueError(f"Invalid date format: {e}")
