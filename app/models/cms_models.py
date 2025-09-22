import datetime
import uuid

from sqlalchemy import (
    Boolean,
    Column,
    UUID,
    DateTime,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import relationship

from app.core.database import Base

# --- Category Models ---


class MerchantSite(Base):
    """
    Represents a Saleor category associated with a merchant.
    """

    __tablename__ = "merchant_site"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        index=True,
        default=lambda: str(uuid.uuid4()),
    )
    merchant_id = Column(String, ForeignKey("merchants.id"))
    site_preffix = Column(String, nullable=True, unique=True)
    site_suffix = Column(String, nullable=True, unique=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.now(datetime.timezone.utc))
    updated_at = Column(DateTime, default=datetime.datetime.now(datetime.timezone.utc))
    merchant = relationship("Merchant", back_populates="merchant_sites")
    merchant_site_carousel_items = relationship(
        "MerchantSiteCarouselItems", back_populates="merchant_site"
    )


class MerchantSiteCarouselItems(Base):
    __tablename__ = "merchant_site_carousel_items"
    id = Column(UUID(as_uuid=True), primary_key=True, index=True)
    merchant_site_id = Column(UUID(as_uuid=True), ForeignKey("merchant_site.id"))
    url = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    order = Column(Integer, nullable=False)

    merchant_site = relationship(
        "MerchantSite", back_populates="merchant_site_carousel_items"
    )
