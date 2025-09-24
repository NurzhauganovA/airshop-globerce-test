# app/controllers/internal_controller.py

from sqlalchemy.orm import Session
from app.controllers.base import BaseController
from app.models.internal_model import Merchant
from app.models.cms_models import MerchantSite
from typing import Optional
from sqlalchemy import or_
from app.schemas.merchant_site_shemas import (
    MerchantSiteCreateSchema,
    MerchantSiteUpdateSchema,
    MerchantSiteSchema,
    MerchantSiteCarouselItemSchema,
)


class MerchantSiteController(
    BaseController[MerchantSite, MerchantSiteCreateSchema, MerchantSiteUpdateSchema]
):
    """
    Controller for handling MerchantSite model operations.
    """

    def get_site_by_preffix(self, db: Session, preffix: str) -> Optional[MerchantSite]:
        return db.query(self._model).filter(self._model.site_preffix == preffix).first()

    def get_merchant_by_suffix(
        self, db: Session, suffix: str
    ) -> Optional[MerchantSite]:
        return db.query(self._model).filter(self._model.site_suffix == suffix).first()

    def get_merchant_for_site(
        self, db: Session, site: MerchantSite
    ) -> Optional[Merchant]:
        return db.query(Merchant).filter(Merchant.site_id == site.id).first()

    def create_merchant_site(
        self, db: Session, *, site: MerchantSiteCreateSchema, merchant_id: str
    ) -> MerchantSite:
        site = MerchantSite(
            **site.model_dump(exclude_none=True), merchant_id=merchant_id
        )
        db.add(site)
        db.commit()
        db.refresh(site)
        return site

    def update_merchant_site(
        self, db: Session, *, site: MerchantSiteUpdateSchema, site_id: str
    ) -> MerchantSite:
        db_site = db.query(self._model).filter(self._model.id == site_id).first()
        if not db_site:
            raise ValueError("Site not found")

        for key, value in site.model_dump(exclude_none=True).items():
            setattr(db_site, key, value)

        db.commit()
        db.refresh(db_site)
        return db_site

    def check_site_existance(self, db: Session, *, preffix: str, suffix: str) -> bool:
        db_site = (
            db.query(self._model)
            .filter(
                or_(
                    self._model.site_preffix == preffix,
                    self._model.site_suffix == suffix,
                )
            )
            .first()
        )
        return bool(db_site)

    def check_merchant_have_site(self, db: Session, *, merchant_id: str) -> bool:
        db_site = (
            db.query(self._model).filter(self._model.merchant_id == merchant_id).first()
        )
        return bool(db_site)

    def get_site_by_merchant_id(
        self, db: Session, *, merchant_id: str
    ) -> Optional[MerchantSite]:
        return (
            db.query(self._model).filter(self._model.merchant_id == merchant_id).first()
        )

    @staticmethod
    def serialize_merchant_site(merchant_site: MerchantSite) -> MerchantSiteSchema:
        """
        Serialize MerchantSite model to MerchantSiteSchema
        """
        return MerchantSiteSchema(
            id=merchant_site.id,
            site_preffix=merchant_site.site_preffix,
            site_suffix=merchant_site.site_suffix,
            is_active=merchant_site.is_active,
            site_carousel_items=[
                MerchantSiteCarouselItemSchema(
                    id=item.id,
                    url=item.url,
                    is_active=item.is_active,
                    order=item.order,
                )
                for item in merchant_site.merchant_site_carousel_items
            ],
        )


# Instantiate the controller classes to be used in your API endpoints
merchant_site_controller = MerchantSiteController(MerchantSite)
