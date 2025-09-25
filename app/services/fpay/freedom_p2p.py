from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Any

import httpx
from httpx import AsyncClient
from sqlalchemy.orm import Session

from app.controllers.transactions_controller import transactions_controller
from app.models.internal_model import Airlink, User, Merchant
from app.models.transaction_models import Transaction
from app.services.fpay import constants


class BaseFreedomP2PService(ABC):
    url: str
    token: str

    @abstractmethod
    def _payload(self) -> dict:
        raise NotImplementedError()

    async def _request(self) -> dict:
        async with AsyncClient() as client:
            response = await client.post(
                url=self.url,
                json=self._payload(),
                headers={
                    "Authorization": f"Basic {self.token}"
                },
            )
            response.raise_for_status()

        return response.json()

    async def process(self) -> dict | None:
        response = await self._request()
        return response


class InitializePaymentFreedomP2PService(BaseFreedomP2PService):

    def __init__(self, airlinks: list[Airlink], merchant: Merchant, user: User) -> None:
        self.airlinks = airlinks
        self.merchant = merchant
        self.user = user

        self.url = constants.FreedomP2PConstants.init_payment_url()
        self.token = constants.FreedomP2PConstants.FREEDOM_P2P_INIT_PAYMENT_TOKEN

    def _generate_order_description(self) -> str:
        airlink = next(iter(self.airlinks), "")
        return airlink and airlink.name

    def _calculate_airlinks_total_price(self) -> str:
        return str(sum((Decimal(airlink.total_price) for airlink in self.airlinks), Decimal("0")))

    def _build_airlinks_payload(self) -> list[dict[str, Any]]:
        return [
            {
                "imageUrl": airlink.first_image_url or "",
                "orderUrl": airlink.public_url or "",
                "orderName": airlink.name or "",
                "price": str(airlink.total_price or ""),
            }
            for airlink in self.airlinks
        ]

    def _payload(self) -> dict:
        return {
            "payment": {
                "sdok": self._calculate_airlinks_total_price(),
                "dscr": f"Оплата за {self._generate_order_description()}",
                "deviceType": "MOBILE",
                "mcc": 2999,
                "payer": {
                    "phoneAcr": self.user.phone_number
                },
                "beneficiary": {
                    "iinBinBcr": self.merchant.bin or "",
                    "nameBcr": self.merchant.legal_name or "",
                    "ibanBcr": self.merchant.iban or "",
                    "addressBcr": self.merchant.primary_address or "",
                    "phoneBcr": self.merchant.phone or "",
                }
            },
            "airlinks": {
                "links": self._build_airlinks_payload(),
            }
        }


class UnholdPaymentFreedomP2PService(BaseFreedomP2PService):
    def __init__(self, freedom_order_reference_id: str) -> None:
        self.freedom_order_reference_id = freedom_order_reference_id

        self.url = (
                constants.FreedomP2PConstants.confirm_payment_url().rstrip("/")
                + f"/{self.freedom_order_reference_id}"
        )
        self.token = constants.FreedomP2PConstants.FREEDOM_P2P_CONFIRM_PAYMENT_TOKEN

    def is_payment_unhold_success(self, response: dict) -> bool:
        unhold_status = response.get("status")
        unhold_msg = response.get("errMsg")

        if not (unhold_status or unhold_msg):
            raise Exception(
                f"UnholdPaymentFreedomP2PService.is_payment_unhold_success status "
                f"and errMsg is empty order_id: {self.freedom_order_reference_id}"
            )

        if unhold_status == constants.FreedomP2PUnholdPaymentConstants.SUCCESS:
            return True

        elif (
                unhold_status == constants.FreedomP2PUnholdPaymentConstants.ERROR
                and constants.FreedomP2PUnholdPaymentConstants.SUCCESS_ERROR_MSG in (unhold_msg or "")
        ):
            return True

        return False

    def _payload(self) -> dict:
        return {
            "reference": self.freedom_order_reference_id
        }


class SetPaymentStatusFreedomP2PService:
    def __init__(self, db: Session, freedom_order_id: str) -> None:
        self.db = db
        self.freedom_order_id = freedom_order_id

    def process(self, status: str, receipt_number: str) -> None:
        statuses = constants.FreedomP2PPaymentStatuses.PAYMENT_STATUS_TO_TRANSACTION_STATUS_MAP
        if status not in statuses:
            return

        transaction = self._get_transaction()

        if transaction is None:
            return

        update_transaction_params = {
            "status": statuses[status],
            "freedom_receipt_number": receipt_number,
        }
        transactions_controller.update(self.db, db_obj=transaction, obj_in=update_transaction_params)

    def _get_transaction(self) -> Transaction | None:
        return transactions_controller.get_transaction_by_freedom_order_id(self.db, self.freedom_order_id)
