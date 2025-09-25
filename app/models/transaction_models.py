import datetime
import uuid

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UUID,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


# --- Transaction Models ---


class Transaction(Base):
    """
    Represents a financial transaction in the system.
    This model acts as a central record for all payment attempts.
    """

    __tablename__ = "transactions"
    __table_args__ = (
        Index("ix_transactions_status_created_at", "status", "created_at"),
        Index("ix_transactions_freedom_order_reference_id", "freedom_order_reference_id"),
    )

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    status = Column(
        String, nullable=False, default="NEW"
    )  # e.g., 'NEW', 'IN_PROGRESS', 'FINISHED', 'REJECTED'
    saleor_order_id = Column(String, nullable=False)  # Links to the Saleor order
    freedom_order_reference_id = Column(String, nullable=True)
    freedom_receipt_number = Column(String, nullable=True)
    synced = Column(Boolean, default=False)
    payment_method_id = Column(
        String, ForeignKey("merchant_payment_methods.id"), nullable=True
    )
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.now(datetime.timezone.utc))
    updated_at = Column(
        DateTime,
        default=datetime.datetime.now(datetime.timezone.utc),
        onupdate=datetime.datetime.now(datetime.timezone.utc),
    )  # pylint: disable=not-callable

    # Relationships
    payment_method = relationship("MerchantPaymentMethod")
    card_requests = relationship("CardRequest", back_populates="transaction")
    loan_requests = relationship("LoanRequest", back_populates="transaction")


class CardRequest(Base):
    """
    Represents a specific card payment request associated with a transaction.
    """

    __tablename__ = "card_requests"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    transaction_id = Column(String, ForeignKey("transactions.id"), nullable=False)
    redirect_url = Column(String, nullable=True)
    fallback_url = Column(String, nullable=True)
    status_url = Column(String, nullable=True)
    status = Column(String, nullable=False)  # e.g., 'PENDING', 'SUCCESS', 'FAILED'
    pg_order_id = Column(String, nullable=True)
    pg_payment_id = Column(String, nullable=True)
    pg_reference = Column(String, nullable=True)
    pg_card_pan = Column(String, nullable=True)
    pg_payment_date = Column(String, nullable=True)
    pg_result = Column(Integer, nullable=True)
    pg_can_reject = Column(Boolean, nullable=True)
    pg_ps_full_amount = Column(Numeric(10, 2), nullable=True)
    pg_net_amount = Column(Numeric(10, 2), nullable=True)

    # Relationship
    transaction = relationship("Transaction", back_populates="card_requests")


class LoanRequest(Base):
    """
    Represents a specific loan request associated with a transaction.
    """

    __tablename__ = "loan_requests"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    transaction_id = Column(String, ForeignKey("transactions.id"), nullable=False)
    redirect_url = Column(String, nullable=True)
    fallback_url = Column(String, nullable=True)
    status_url = Column(String, nullable=True)
    status = Column(String, nullable=False)  # e.g., 'PENDING', 'SUCCESS', 'FAILED'
    iin = Column(String, nullable=True)
    apply_code = Column(String, nullable=True)
    selected_offer = Column(String, ForeignKey("loan_offers.id"), nullable=True)
    mfo_uuid = Column(UUID(as_uuid=True), nullable=True)
    raw_json_response = Column(JSON, nullable=True)
    mobile_phone = Column(String, nullable=True)

    # Relationships
    transaction = relationship("Transaction", back_populates="loan_requests")
    loan_offers = relationship(
        "LoanOffer",
        back_populates="loan_request",
        foreign_keys="[LoanOffer.loan_request_id]",
    )


class LoanOffer(Base):
    """
    Represents a specific loan offer returned from a loan request.
    """

    __tablename__ = "loan_offers"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    loan_request_id = Column(String, ForeignKey("loan_requests.id"), nullable=False)
    loan_type = Column(String, nullable=False)
    period = Column(Integer, nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    suitable = Column(Boolean, default=False)
    outer_id = Column(String, nullable=True)

    # Relationship
    loan_request = relationship(
        "LoanRequest", back_populates="loan_offers", foreign_keys=[loan_request_id]
    )
