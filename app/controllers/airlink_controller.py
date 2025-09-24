import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy.orm import Session

from app.controllers.base import BaseController
from app.core.config import settings
from app.models.internal_model import Airlink, AirlinkImage, AirlinkCheckoutItem
from app.schemas.airlink_schemas import (
    AirlinkCreateRequest,
    AirlinkUpdateRequest,
    AirlinkProductSchema,
    AirlinkImages,
)


class AirlinkController(
    BaseController[Airlink, AirlinkCreateRequest, AirlinkUpdateRequest]
):
    """
    Controller for handling Airlink model operations.
    """

    def create_airlink(self, db: Session, airlink_in: AirlinkCreateRequest) -> Airlink:
        """
        Creates a new Airlink entry in the database, including its products, variants, and images.
        """
        airlink_id = str(uuid.uuid4())
        db_airlink = Airlink(
            id=airlink_id,
            name=airlink_in.name,
            description=airlink_in.description,
            date_start=airlink_in.date_start,
            date_end=airlink_in.date_end,
            merchant_id=airlink_in.merchant_id,
            planned_price=airlink_in.planned_price,
            moderation_status="PENDING",  # Default status
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(db_airlink)
        db.flush()  # Flush to get the airlink.id for related objects

        self._add_products_to_airlink(db, db_airlink, airlink_in.products)
        self._add_images_to_airlink(db, db_airlink, airlink_in.images)

        self._recalculate_total_price(db_airlink)
        db.commit()
        db.refresh(db_airlink)
        return db_airlink

    # implements adding images to airlink
    def _add_images_to_airlink(
            self, db: Session, db_airlink: Airlink, images: Optional[List[AirlinkImages]]
    ):
        """
        Adds images to an Airlink.
        """
        for img_in in images or []:
            db_image = AirlinkImage(
                id=str(uuid.uuid4()),
                airlink_id=db_airlink.id,
                url=str(img_in.url),
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            db.add(db_image)

    def _add_products_to_airlink(
            self,
            db: Session,
            db_airlink: Airlink,
            products: Optional[List[AirlinkProductSchema]],
    ):
        """
        Adds products and their variants as checkout items to an Airlink.
        """
        for product_in in products or []:
            for variant_in in product_in.variants:
                db_checkout_item = AirlinkCheckoutItem(
                    id=str(uuid.uuid4()),
                    airlink_id=db_airlink.id,
                    saleor_variant_id=variant_in.variant_id,
                    quantity=variant_in.stock_quantity,
                    # Assuming stock_quantity from schema is the quantity for airlink
                    price=variant_in.price,
                )
                db.add(db_checkout_item)

    def get_airlink_by_id(self, db: Session, airlink_id: str) -> Optional[Airlink]:
        """
        Retrieves an Airlink by its ID, including its related images and checkout items.
        """
        return db.query(Airlink).filter(Airlink.id == airlink_id).first()

    # implements recalculation of total price for airlink
    def _recalculate_total_price(self, db_airlink: Airlink):
        """
        Recalculates the total price of an Airlink based on its checkout items.
        """
        total_price = sum(
            item.price * item.quantity for item in db_airlink.checkout_items
        )
        db_airlink.total_price = total_price

    def update_airlink(
            self, db: Session, db_airlink: Airlink, airlink_update: AirlinkUpdateRequest
    ) -> Airlink:
        """
        Updates an existing Airlink.
        """
        update_data = airlink_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            if field == "products":
                # Clear existing products and add new ones if provided
                db.query(AirlinkCheckoutItem).filter(
                    AirlinkCheckoutItem.airlink_id == db_airlink.id
                ).delete()
                self._add_products_to_airlink(db, db_airlink, value)
                self._recalculate_total_price(db_airlink)
            elif field == "images":
                # Clear existing images and add new ones if provided
                db.query(AirlinkImage).filter(
                    AirlinkImage.airlink_id == db_airlink.id
                ).delete()
                self._add_images_to_airlink(db, db_airlink, value)
            else:
                setattr(db_airlink, field, value)

        db_airlink.updated_at = datetime.now(timezone.utc)
        db.add(db_airlink)
        db.commit()
        db.refresh(db_airlink)
        return db_airlink

    def publish_airlink(self, db: Session, db_airlink: Airlink) -> Airlink:
        """
        Publishes an Airlink.
        """
        db_airlink.published = True
        db_airlink.updated_at = datetime.now(timezone.utc)

        db_airlink.public_url = (
            f"{settings.LINK_FRONT_URL}/{settings.LINK_PATH_PREFIX}/{db_airlink.id}"
        )

        db.add(db_airlink)
        db.commit()
        db.refresh(db_airlink)
        return db_airlink

    def unpublish_airlink(self, db: Session, db_airlink: Airlink) -> Airlink:
        """
        Unpublishes an Airlink.
        """
        db_airlink.published = False
        db_airlink.updated_at = datetime.now(timezone.utc)
        db.add(db_airlink)
        db.commit()
        db.refresh(db_airlink)
        return db_airlink


airlink_controller = AirlinkController(Airlink)
