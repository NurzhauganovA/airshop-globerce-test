# app/services/order/order_confirmation_service.py

import secrets
from typing import Any, Dict, List, Optional, Union

from app.services.saleor import SaleorService

class OrderConfirmationService:

    def __init__(self, saleor: SaleorService):
        self.saleor = saleor

    async def get_order(self, order_id: str):
        resp = await self.saleor.client.get_order_by_id(order_id=order_id)
        return getattr(resp, "order", None)

    @staticmethod
    def metadata_to_dict(rows: Optional[List[Union[Dict[str, Any], Any]]]) -> Dict[str, str]:

        out: Dict[str, str] = {}
        for item in rows or []:
            if item is None:
                continue
            if isinstance(item, dict):
                k = item.get("key")
                v = item.get("value")
            else:
                # pydantic-модели
                k = getattr(item, "key", None)
                v = getattr(item, "value", None)
            if isinstance(k, str) and isinstance(v, str):
                out[k] = v
        return out

    @staticmethod
    def is_fulfilled(order) -> bool:
        status = getattr(order.status, "value", order.status)
        return str(status) == "FULFILLED"

    @staticmethod
    def generate_otp() -> int:
        # 6-значный код 100000..999999 (без ведущих нулей)
        return secrets.randbelow(900_000) + 100_000