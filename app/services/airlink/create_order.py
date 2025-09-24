from datetime import datetime, timezone
from typing import Optional, Set

from fastapi import HTTPException
from sqlalchemy.orm import Session
from starlette import status

from app.controllers import transactions_controller
from app.core.config import settings
from app.graphql.generated_client import (
    CreateCheckoutFromAirlinkCheckoutCreate,
    CreateOrderFromSaleorCheckout,
)
from app.models.internal_model import Airlink, AirlinkCheckoutItem
from app.services.saleor import SaleorService


class CreateOrderByAirlinkService:

    def __init__(
            self,
            airlink: Airlink,
            saleor_service: SaleorService,
            customer_id: str,
            customer_email: str,
            payment_method_id: str | None = None,
            saleor_channel_id: str = settings.LINK_SALEOR_CHANNEL_ID,
    ) -> None:
        self.airlink = airlink
        self.saleor_service = saleor_service
        self.payment_method_id = payment_method_id
        self.saleor_channel_id = saleor_channel_id
        self.customer_id = customer_id
        self.customer_email = customer_email

        self._is_validated = False

    @property
    def valid_payment_method_ids(self) -> Set[str]:
        return {
            mpm.id for mpm in self.airlink.merchant.merchant_payment_methods if mpm.active
        }

    def validate_airlink(self) -> None:
        if not self.airlink:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Airlink not found",
            )

        if not self.airlink.published:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Airlink is not published.",
            )

        now = datetime.now(timezone.utc)
        date_start = self._as_aware_utc(self.airlink.date_start)
        if date_start and now < date_start:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Airlink is not active yet.",
            )

        date_end = self._as_aware_utc(self.airlink.date_end)
        if date_end and now > date_end:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Airlink has expired.",
            )

        if not self.airlink.checkout_items:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Airlink has no items to order.",
            )

        if len(self.airlink.checkout_items) > 1:
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="Ordering from an Airlink with multiple items is not yet supported.",
            )

        if not self.airlink.merchant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Merchant not found for this Airlink.",
            )

        if self.payment_method_id and self.payment_method_id not in self.valid_payment_method_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid payment method for this merchant.",
            )

        self._is_validated = True

    async def _resolve_channel_slug(self) -> str:
        response = await self.saleor_service.client.get_channel_by_id(self.saleor_channel_id)
        if not (response.channel and response.channel.slug):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not resolve Saleor channel.",
            )
        return response.channel.slug

    @staticmethod
    def _raise_checkout_error(checkout: CreateCheckoutFromAirlinkCheckoutCreate) -> None:
        errors = [*checkout.checkout_errors, *checkout.errors]
        if errors:
            messages = [err.message for err in errors if err.message]
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Could not create checkout in Saleor: {'; '.join(messages)}",
            )

        if not (checkout.checkout and checkout.checkout.id):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Saleor created a checkout but did not return an ID.",
            )

    @staticmethod
    def _raise_order_error(order_response: CreateOrderFromSaleorCheckout) -> None:
        order_result = order_response.order_create_from_checkout

        if order_result.errors:
            messages = [err.message for err in order_result.errors if err.message]
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Could not create order from checkout in Saleor: {'; '.join(messages)}",
            )

        if not (order_result.order and order_result.order.id):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Saleor created an order but did not return an ID.",
            )

    async def create_checkout(
            self,
            checkout_item: AirlinkCheckoutItem,
            customer_id: str,
            channel_slug: str,
            email: str,
    ) -> CreateCheckoutFromAirlinkCheckoutCreate:
        response = await self.saleor_service.client.create_checkout_from_airlink(
            variant_id=checkout_item.saleor_variant_id,
            price=self.airlink.planned_price,
            customer_id=customer_id,
            airlink_id=self.airlink.id,
            channel_slug=channel_slug,
            email=email,
        )
        checkout = response.checkout_create
        self._raise_checkout_error(checkout)
        return checkout

    async def create_saleor_order(self, checkout_id: str) -> CreateOrderFromSaleorCheckout:
        saleor_order_response = await self.saleor_service.client.create_order_from_saleor_checkout(
            checkout_id=checkout_id,
            merchant_id=self.airlink.merchant_id,
        )
        self._raise_order_error(saleor_order_response)
        return saleor_order_response

    def create_transaction(self, db: Session, saleor_order_id: str) -> None:
        transaction = transactions_controller.create_transaction(
            db=db,
            saleor_order_id=saleor_order_id,
            amount=self.airlink.planned_price,
        )
        transactions_controller.set_transaction_payment_type(
            db=db,
            transaction=transaction,
            payment_method_id=self.payment_method_id,
        )

    async def create_order(self) -> str:
        if not self._is_validated:
            self.validate_airlink()

        checkout_item = self.airlink.checkout_items[0]
        channel_slug = await self._resolve_channel_slug()

        try:
            checkout_response = await self.create_checkout(
                checkout_item=checkout_item,
                customer_id=self.customer_id,
                channel_slug=channel_slug,
                email=self.customer_email,
            )
            order_response = await self.create_saleor_order(checkout_response.checkout.id)
            return order_response.order_create_from_checkout.order.id
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"An error occurred during Saleor order creation: {exc}",
            ) from exc

    async def process(self, db: Session) -> str:
        saleor_order_id = await self.create_order()
        self.create_transaction(db=db, saleor_order_id=saleor_order_id)
        return saleor_order_id

    @staticmethod
    def _as_aware_utc(value: Optional[datetime]) -> Optional[datetime]:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
