from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field
from app.models.internal_model import Merchant


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
    first_name: str
    middle_name: str
    last_name: str
    profile_id: str
    external_id: str

class MerchantOnboardResponse(BaseModel):
    status: str
    merchant_id: str
    message: str

class MerchantOnboardRequest(BaseModel):
    name: str
    bin: str = Field(..., min_length=12, max_length=12)
    bank_account: str
    phone: str
    company_id: str
    company_type: str = Field(..., pattern="^(LLC|IP)$")
    registration_date: str
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
            registration_date=self.registration_date,
        )
