# app/models/internal_models.py

import datetime
import uuid

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Table,
    Text,
    UUID,
)
from sqlalchemy.dialects.postgresql import INT4RANGE
from sqlalchemy.orm import relationship

from app.core.database import Base

# Import other models to ensure they are registered with SQLAlchemy's Base
from app.models.category_models import MerchantCategory
from app.models.cms_models import MerchantSite
from app.models.warehouse_models import MerchantShippingZone


# Many-to-many association table for Merchant and User (MerchantEmployee)
merchant_employee_association = Table(
    "merchant_employee_association",
    Base.metadata,
    Column("user_id", String, ForeignKey("users.id"), primary_key=True),
    Column("merchant_id", String, ForeignKey("merchants.id"), primary_key=True),
)

# Many-to-many association table for Customer and Address (CustomerDeliveryAddress)
customer_delivery_address_association = Table(
    "customer_delivery_addresses",
    Base.metadata,
    Column("customer_id", String, ForeignKey("customers.id"), primary_key=True),
    Column("address_id", String, ForeignKey("addresses.id"), primary_key=True),
)


class User(Base):
    """
    Represents a user (customer or merchant) in our internal database.
    This is separate from Saleor's user management to allow for custom
    authentication and roles.
    """

    __tablename__ = "users"

    # Changed ID to be a UUID. It's stored as a string in the database.
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    phone_number = Column(String, unique=True, index=True, nullable=True)
    # New column to store the hashed password.
    password_hash = Column(String, nullable=False)

    # New optional fields
    username = Column(String, index=True, nullable=True)
    email = Column(String, unique=True, index=True, nullable=True)

    is_merchant = Column(Boolean, default=False)
    is_admin = Column(Boolean, default=False)
    is_technical = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.now(datetime.timezone.utc))
    updated_at = Column(
        DateTime,
        default=datetime.datetime.now(datetime.timezone.utc),
        onupdate=datetime.datetime.now(datetime.timezone.utc),
    )

    # Relationship to Merchant through the association table
    merchants = relationship(
        "Merchant", secondary=merchant_employee_association, back_populates="employees"
    )
    sessions = relationship(
        "UserSession", back_populates="user", cascade="all, delete-orphan"
    )
    customer_profile = relationship(
        "Customer", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    employee_profile = relationship(
        "EmployeeProfile",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )


class Merchant(Base):
    """
    Represents a merchant in our internal database. This can hold
    specific information related to the merchant's shop, which may not
    be available directly in the Saleor API.
    """

    __tablename__ = "merchants"

    # Changed ID to be a UUID
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    # Name changed to legal_name
    legal_name = Column(String, index=True, nullable=False)
    # New field for the Business Identification Number
    bin = Column(String(12), unique=True, nullable=False)
    iban = Column(String, nullable=True)

    mid = Column(String, nullable=True)
    mcc = Column(String, nullable=True)
    oked = Column(String, nullable=True)
    tid = Column(String, nullable=True)

    # Removed saleor_shop_id and user_id as per request
    phone = Column(String, nullable=True)
    company_id = Column(String, nullable=True)
    company_type = Column(String, nullable=True)
    registration_date = Column(DateTime, nullable=True)

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.now(datetime.timezone.utc))
    updated_at = Column(
        DateTime,
        default=datetime.datetime.now(datetime.timezone.utc),
        onupdate=datetime.datetime.now(datetime.timezone.utc),
    )

    # Relationship to User (MerchantEmployee) through the association table
    employees = relationship(
        "User", secondary=merchant_employee_association, back_populates="merchants"
    )
    addresses = relationship(
        "MerchantAddress", back_populates="merchant", cascade="all, delete-orphan"
    )
    merchant_payment_methods = relationship(
        "MerchantPaymentMethod", back_populates="merchant", cascade="all, delete-orphan"
    )

    merchant_categories = relationship(
        "MerchantCategory", back_populates="merchant", cascade="all, delete-orphan"
    )

    merchant_sites = relationship(
        "MerchantSite", back_populates="merchant", cascade="all, delete-orphan"
    )

    merchant_shipping_zones = relationship(
        "MerchantShippingZone", back_populates="merchant", cascade="all, delete-orphan"
    )


class Customer(Base):
    """
    Represents a customer's profile, extending the base User model.
    """

    __tablename__ = "customers"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False, unique=True)

    first_name = Column(String, nullable=True)
    surname = Column(String, nullable=True)
    middle_name = Column(String, nullable=True)
    default_locale = Column(String, nullable=True)
    entry_merchant_id = Column(String, ForeignKey("merchants.id"), nullable=True)

    # Relationship to User
    user = relationship("User", back_populates="customer_profile")

    # Relationship to Address through the association table
    delivery_addresses = relationship(
        "Address",
        secondary=customer_delivery_address_association,
        back_populates="delivery_for_customers",
    )


class Country(Base):
    """
    Represents a country with multilingual names and postal code ranges.
    """

    __tablename__ = "countries"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    # JSON field to store translations for names (e.g., {"ru": "Россия", "kk": "Қазақстан", "en": "Kazakhstan"})
    name = Column(JSON, nullable=False)
    currency_code = Column(String, nullable=False)
    # JSON field to store a list of postal code ranges, e.g., [{"start": "01000", "end": "05000"}]
    postal_codes_range = Column(JSON, nullable=True)


class City(Base):
    """
    Represents a city with multilingual names and a foreign key to its country.
    """

    __tablename__ = "cities"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    # JSON field to store translations for names (e.g., {"ru": "Алматы", "kk": "Алматы", "en": "Almaty"})
    name = Column(JSON, nullable=False)
    # Foreign key to the Country table
    country_id = Column(String, ForeignKey("countries.id"), nullable=False)

    # Relationship back to the Country model
    country = relationship("Country")


class Address(Base):
    """
    Represents a generic address.
    """

    __tablename__ = "addresses"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    contact_phone = Column(String, nullable=True)
    address_line_1 = Column(String, nullable=False)
    address_line_2 = Column(String, nullable=True)
    address_line_3 = Column(String, nullable=True)

    country_id = Column(String, ForeignKey("countries.id"), nullable=True)
    city_id = Column(String, ForeignKey("cities.id"), nullable=True)

    creator_id = Column(String, ForeignKey("users.id"), nullable=True)

    created_at = Column(DateTime, default=datetime.datetime.now(datetime.timezone.utc))
    modified_at = Column(
        DateTime,
        default=datetime.datetime.now(datetime.timezone.utc),
        onupdate=datetime.datetime.now(datetime.timezone.utc),
    )

    # Relationships
    country = relationship("Country")
    city = relationship("City")
    creator = relationship("User")

    # Relationship to customers who use this address
    delivery_for_customers = relationship(
        "Customer",
        secondary=customer_delivery_address_association,
        back_populates="delivery_addresses",
    )
    merchant_associations = relationship(
        "MerchantAddress", back_populates="address", cascade="all, delete-orphan"
    )


class MerchantAddress(Base):
    """
    Association object between Merchant and Address, with additional data.
    """

    __tablename__ = "merchant_addresses"

    merchant_id = Column(String, ForeignKey("merchants.id"), primary_key=True)
    address_id = Column(String, ForeignKey("addresses.id"), primary_key=True)
    type = Column(String, nullable=False)  # e.g., 'PRIMARY', 'WAREHOUSE'
    warehouse_saleor_id = Column(String, nullable=True)

    # Relationships
    merchant = relationship("Merchant", back_populates="addresses")
    address = relationship("Address", back_populates="merchant_associations")


# --- Payment-related Models ---


class BasePaymentMethod(Base):
    """
    Represents a base payment method with general configuration.
    """

    __tablename__ = "base_payment_methods"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    type = Column(String, nullable=False)  # e.g., 'CARD', 'LOAN'
    loan_type = Column(String, nullable=True)  # e.g., 'INSTALLMENT', 'CREDIT'
    loan_period_range = Column(
        INT4RANGE, nullable=True
    )  # e.g., [{"start": 1, "end": 12}, {"start": 2, "end": 24}]
    enabled = Column(Boolean, default=True)

    # Relationships to merchant-specific configurations
    merchant_methods = relationship(
        "MerchantPaymentMethod", back_populates="base_method"
    )


class MerchantPaymentMethod(Base):
    """
    Represents a specific payment method enabled for a merchant.
    """

    __tablename__ = "merchant_payment_methods"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    base_payment_method_id = Column(
        String, ForeignKey("base_payment_methods.id"), nullable=False
    )
    merchant_id = Column(String, ForeignKey("merchants.id"), nullable=False)
    active = Column(Boolean, default=True)

    # Relationships
    base_method = relationship("BasePaymentMethod", back_populates="merchant_methods")
    merchant = relationship("Merchant")

    mfo_configs = relationship("MFOConfig", back_populates="merchant_payment_method")
    fpay_configs = relationship("FPayConfig", back_populates="merchant_payment_method")


class MFOConfig(Base):
    """
    Represents a specific MFO (Microfinance Organization) configuration for a merchant's
    payment method.
    """

    __tablename__ = "mfo_configs"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    merchant_payment_method_id = Column(
        String, ForeignKey("merchant_payment_methods.id"), nullable=False
    )
    product_code = Column(String, nullable=True)
    partner_code = Column(String, nullable=True)
    period_range = Column(INT4RANGE, nullable=True)  # e.g., [{"start": 3, "end": 6}]

    # Relationship
    merchant_payment_method = relationship(
        "MerchantPaymentMethod", back_populates="mfo_configs"
    )


class FPayConfig(Base):
    """
    Represents a specific FPay (Financial Payment) configuration for a merchant's
    payment method.
    """

    __tablename__ = "fpay_configs"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    merchant_payment_method_id = Column(
        String, ForeignKey("merchant_payment_methods.id"), nullable=False
    )
    fpay_merchant_id = Column(String, nullable=False)
    secret_key = Column(String, nullable=False)

    # Relationship
    merchant_payment_method = relationship(
        "MerchantPaymentMethod", back_populates="fpay_configs"
    )


class Airlink(Base):
    """
    Represents an Airlink, a custom checkout preset created by a merchant.
    """

    __tablename__ = "airlinks"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    moderation_status = Column(String, nullable=False, default="PENDING")
    name = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    date_start = Column(DateTime, nullable=True)
    date_end = Column(DateTime, nullable=True)
    merchant_id = Column(String, ForeignKey("merchants.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.now(datetime.timezone.utc))
    updated_at = Column(
        DateTime,
        default=datetime.datetime.now(datetime.timezone.utc),
        onupdate=datetime.datetime.now(datetime.timezone.utc),
    )  # pylint: disable=not-callable
    total_price = Column(Numeric(10, 2), nullable=True)
    planned_price = Column(Numeric(10, 2), nullable=True)
    published = Column(Boolean, default=False)
    public_url = Column(String, nullable=True)
    ai_response = Column(JSON, nullable=True)

    # Relationships
    merchant = relationship("Merchant")
    images = relationship("AirlinkImage", back_populates="airlink")
    checkout_items = relationship("AirlinkCheckoutItem", back_populates="airlink")


class AirlinkImage(Base):
    """
    Represents an image for an Airlink.
    """

    __tablename__ = "airlink_images"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    url = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.now(datetime.timezone.utc))
    updated_at = Column(
        DateTime,
        default=datetime.datetime.now(datetime.timezone.utc),
        onupdate=datetime.datetime.now(datetime.timezone.utc),
    )  # pylint: disable=not-callable
    airlink_id = Column(String, ForeignKey("airlinks.id"), nullable=False)

    # Relationship
    airlink = relationship("Airlink", back_populates="images")


class AirlinkCheckoutItem(Base):
    """
    Represents a specific product variant in an Airlink checkout.
    """

    __tablename__ = "airlink_checkout_items"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    airlink_id = Column(String, ForeignKey("airlinks.id"), nullable=False)
    saleor_variant_id = Column(String, nullable=False)
    quantity = Column(Integer, nullable=False)
    price = Column(Numeric(10, 2), nullable=False)

    # Relationship
    airlink = relationship("Airlink", back_populates="checkout_items")


class UserSession(Base):
    """
    Stores active user sessions, allowing them to be revoked.
    """

    __tablename__ = "user_sessions"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    jti = Column(String, unique=True, nullable=False, index=True)  # JWT ID
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    validation_type = Column(String, nullable=False, default="none")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.now(datetime.timezone.utc))
    expires_at = Column(DateTime, nullable=False)

    user = relationship("User", back_populates="sessions")


class EmployeeProfile(Base):

    __tablename__ = "employee_profiles"
    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    middle_name = Column(String, nullable=True)
    profile_id = Column(String, nullable=True)
    external_id = Column(String, nullable=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)

    user = relationship("User", back_populates="employee_profile")
