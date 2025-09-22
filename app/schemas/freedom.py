import secrets
import string
from datetime import datetime
from typing import Optional, Dict, Any

from app.graphql.generated_client import BaseModel


class Store(BaseModel):
    id: Optional[str] = None
    bin: Optional[str] = None
    name: Optional[str] = None
    phone: Optional[str] = None
    bank_account: Optional[str] = None
    registration_date: Optional[datetime] = None


class Customer(BaseModel):
    iin: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None


class FPayCardPaymentRequestDto(BaseModel):
    order_id: Optional[str] = None
    merchant_id: Optional[str] = None
    secret_key: Optional[str] = None
    amount: Optional[int] = None
    description: Optional[str] = None
    salt: Optional[str] = None
    template: Optional[str] = None
    auto_clearing: Optional[int] = None
    result_url: Optional[str] = None
    success_url: Optional[str] = None
    failure_url: Optional[str] = None
    request_method: Optional[str] = None
    success_url_method: Optional[str] = None
    signature: Optional[str] = None
    raw_request: Optional[str] = None
    payment_id: Optional[str] = None

    def _secure_random_alphanumeric(self, length: int) -> str:
        chars = string.ascii_letters + string.digits
        return "".join(secrets.choice(chars) for _ in range(length))

    def to_form_data(self) -> Dict[str, Any]:
        """Формирует словарь в формате FreedomPay API (pg_*)"""
        form_data = {}

        if self.order_id:
            form_data["pg_order_id"] = self.order_id
        if self.merchant_id:
            form_data["pg_merchant_id"] = self.merchant_id
        if self.amount is not None:
            form_data["pg_amount"] = str(self.amount)  # как в Java: .toString()
        if self.description:
            form_data["pg_description"] = self.description
        form_data["pg_salt"] = self._secure_random_alphanumeric(length=8)
        if self.template:
            form_data["pg_template"] = self.template
        if self.auto_clearing is not None:
            form_data["pg_auto_clearing"] = self.auto_clearing
        if self.result_url:
            form_data["pg_result_url"] = self.result_url
        if self.success_url:
            form_data["pg_success_url"] = self.success_url
        if self.failure_url:
            form_data["pg_failure_url"] = self.failure_url
        if self.request_method:
            form_data["pg_request_method"] = self.request_method
        if self.success_url_method:
            form_data["pg_success_url_method"] = self.success_url_method
        if self.payment_id:
            form_data["pg_payment_id"] = self.payment_id

        return form_data
