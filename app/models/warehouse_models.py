import datetime
import uuid

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    String,
    Table,
    UUID,
)
from sqlalchemy.orm import relationship

from app.core.database import Base

# --- Association Table ---

merchant_shipping_zone_warehouse_association = Table(
    "merchant_shipping_zone_warehouse_association",
    Base.metadata,
    Column(
        "shipping_zone_id",
        UUID(as_uuid=True),
        ForeignKey("merchant_shipping_zone.id"),
        primary_key=True,
    ),
    Column(
        "warehouse_id", String, ForeignKey("merchant_warehouse.id"), primary_key=True
    ),
)


# --- Warehouse Models ---


class MerchantWarehouse(Base):
    """
    Represents a merchant's warehouse, which corresponds to a Saleor Warehouse.
    """

    __tablename__ = "merchant_warehouse"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    saleor_warehouse_id = Column(String, nullable=False)
    merchant_id = Column(String, ForeignKey("merchants.id"), nullable=False)
    address_id = Column(String, ForeignKey("addresses.id"), nullable=True)

    shipping_zones = relationship(
        "MerchantShippingZone",
        secondary=merchant_shipping_zone_warehouse_association,
        back_populates="warehouses",
    )
    address = relationship("Address")



class MerchantShippingZone(Base):
    """
    Represents a Saleor shipping zone associated with a merchant.
    """

    __tablename__ = "merchant_shipping_zone"
    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    merchant_id = Column(String, ForeignKey("merchants.id"))
    saleor_shipping_zone_id = Column(String, nullable=False)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.now(datetime.timezone.utc))
    updated_at = Column(
        DateTime,
        default=datetime.datetime.now(datetime.timezone.utc),
        onupdate=datetime.datetime.now(datetime.timezone.utc),
    )
    merchant = relationship("Merchant", back_populates="merchant_shipping_zones")
    warehouses = relationship(
        "MerchantWarehouse",
        secondary=merchant_shipping_zone_warehouse_association,
        back_populates="shipping_zones",
    )
