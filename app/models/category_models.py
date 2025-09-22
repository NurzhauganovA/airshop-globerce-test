import uuid

from sqlalchemy import (
    Column,
    ForeignKey,
    String,
)
from sqlalchemy.orm import relationship

from app.core.database import Base

# --- Category Models ---


class MerchantCategory(Base):
    """
    Represents a Saleor category associated with a merchant.
    """

    __tablename__ = "merchant_category"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    saleor_category_id = Column(String, nullable=False)
    merchant_id = Column(String, ForeignKey("merchants.id"), nullable=False)

    merchant = relationship("Merchant", back_populates="merchant_categories")
