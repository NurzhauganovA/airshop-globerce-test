# app/controllers/internal/merchant_controller.py

from typing import List

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.internal_model import (
    Address,
    BasePaymentMethod,
    Merchant,
    MerchantAddress,
    MerchantPaymentMethod,
    MFOConfig,
    Airlink,
    EmployeeProfile, User,
)
from app.schemas.integrations import MerchantAddressCreate
from app.models.category_models import MerchantCategory
from app.models.warehouse_models import MerchantShippingZone, MerchantWarehouse


def get_by_bin(db: Session, *, bin: str) -> Merchant | None:
    """
    Get a merchant by Business Identification Number (BIN).
    """
    return db.query(Merchant).filter(Merchant.bin == bin).first()

async def get_by_bin_async(db: AsyncSession, *, bin: str) -> Merchant | None:
    """
    Get a merchant by Business Identification Number (BIN).
    """
    result = await db.execute(select(Merchant).filter(Merchant.bin == bin))
    return result.scalars().first()





def create_merchant(db: Session, *, merchant: Merchant):
    """
    Create merchant's employees. Add some other
    """
    if get_by_bin(db, bin=merchant.bin):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A merchant with this BIN already exists.",
        )

    db.add(merchant)
    db.flush()
    db.refresh(merchant)
    return merchant

async def create_merchant_async(db: AsyncSession, *, merchant: Merchant):
    """
    Create merchant's employees. Add some other
    """
    if await get_by_bin_async(db=db, bin=merchant.bin):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A merchant with this BIN already exists.",
        )
    
    db.add(merchant)
    await db.flush()
    await db.refresh(merchant)
    return merchant




def add_address_to_merchant(
    db: Session, *, merchant: Merchant, address_data: MerchantAddressCreate
) -> MerchantAddress:
    """
    Creates an address and associates it with a merchant.
    """
    new_address = Address(
        name=address_data.name,
        contact_phone=address_data.contact_phone,
        address_line_1=address_data.address_line_1,
        address_line_2=address_data.address_line_2,
        address_line_3=address_data.address_line_3,
        country_id=address_data.country_id,
        city_id=address_data.city_id,
    )
    db.add(new_address)

    merchant_address = MerchantAddress(
        merchant=merchant, address=new_address, type=address_data.type
    )
    db.add(merchant_address)
    db.flush()
    return merchant_address


def setup_default_payment_methods(
    db: Session, *, merchant: Merchant
) -> List[MerchantPaymentMethod]:
    """
    Sets up default enabled payment methods for a given merchant.
    """
    enabled_base_methods = (
        db.query(BasePaymentMethod).filter(BasePaymentMethod.enabled.is_(True)).all()
    )

    merchant_payment_methods = []
    for base_method in enabled_base_methods:
        merchant_payment_method = MerchantPaymentMethod(
            base_payment_method_id=base_method.id, merchant_id=merchant.id, active=True
        )
        db.add(merchant_payment_method)
        merchant_payment_methods.append(merchant_payment_method)

    db.flush()
    return merchant_payment_methods

async def setup_default_payment_methods_async(
        db: AsyncSession, *, merchant: Merchant
) -> List[MerchantPaymentMethod]:
    enabled_base_methods_results = (
        await db.execute(select(BasePaymentMethod).filter(BasePaymentMethod.enabled.is_(True)))
    )
    enabled_base_methods = enabled_base_methods_results.scalars().all()
    merchant_payment_methods = []
    for base_method in enabled_base_methods:
        merchant_payment_method = MerchantPaymentMethod(
            base_payment_method_id=base_method.id, merchant_id=merchant.id, active=True
        )
        db.add(merchant_payment_method)
        merchant_payment_methods.append(merchant_payment_method)

    await db.flush()
    return merchant_payment_methods

def add_category_to_merchant(
    db: Session, *, merchant: Merchant, category_id: str
) -> MerchantCategory:
    """
    adds category to mechant
    """
    categories = (
        db.query(MerchantCategory)
        .filter(
            MerchantCategory.merchant_id == merchant.id,
            MerchantCategory.saleor_category_id == category_id,
        )
        .all()
    )
    if len(categories) > 0:
        return categories[0]

    new_category = MerchantCategory(
        saleor_category_id=category_id, merchant_id=merchant.id
    )

    db.add(new_category)
    db.commit()
    db.refresh(new_category)

    return new_category


def get_merchant_by_id(db: Session, *, merchant_id: str) -> Merchant | None:
    """
    Get a merchant by ID.
    """
    return db.query(Merchant).filter(Merchant.id == merchant_id).first()


def add_shipping_zone_to_merchant(
    db: Session, *, merchant: Merchant, shipping_zone_id: str, shipping_zone_name: str
) -> MerchantShippingZone:
    """
    adds category to mechant
    """
    shipping_zones = (
        db.query(MerchantShippingZone)
        .filter(
            MerchantShippingZone.merchant_id == merchant.id,
            MerchantShippingZone.saleor_shipping_zone_id == shipping_zone_id,
        )
        .all()
    )
    if len(shipping_zones) > 0:
        return shipping_zones[0]

    new_shipping_zone = MerchantShippingZone(
        saleor_shipping_zone_id=shipping_zone_id,
        name=shipping_zone_name,
        merchant_id=merchant.id,
    )

    db.add(new_shipping_zone)
    db.commit()
    db.refresh(new_shipping_zone)

    return new_shipping_zone


def add_mfo_periods(
    db: Session, *, payment_methods: List[MerchantPaymentMethod], periods: dict
):
    result = []
    for el in periods:
        for period in el["period_limits"]:
            payment_method = next(
                filter(
                    lambda pm: pm.base_method.type == "LOAN"
                    and pm.base_method.loan_type == el["loan_type"]
                    and period in pm.base_method.loan_period_range,
                    payment_methods,
                ),
                None,
            )
            if payment_method is None:
                continue
            mfo_config = MFOConfig(
                merchant_payment_method=payment_method,
                product_code=el["outer_code"],
                period_range=period,
            )
            db.add(mfo_config)
            result.append(mfo_config)
    db.commit()
    return result


def list_shipping_zones_for_merchant(
    db: Session, *, merchant_id: str
) -> List[MerchantShippingZone]:
    """
    Get a merchant by ID.
    """
    return (
        db.query(MerchantShippingZone)
        .filter(MerchantShippingZone.merchant_id == merchant_id)
        .all()
    )


def get_merchant_shipping_zone_by_name(
    db: Session, *, merchant_id: str, shipping_zone_name: str
) -> MerchantShippingZone | None:
    """
    Get a merchant shipping zone by name for a specific merchant.
    """
    return (
        db.query(MerchantShippingZone)
        .filter(
            MerchantShippingZone.merchant_id == merchant_id,
            MerchantShippingZone.name == shipping_zone_name,
        )
        .first()
    )


def get_merchant_shipping_zone_by_id(
    db: Session, *, merchant_id: str, id: str
) -> MerchantShippingZone | None:
    """
    Get a merchant shipping zone by id for a specific merchant.
    """
    return (
        db.query(MerchantShippingZone)
        .filter(
            MerchantShippingZone.merchant_id == merchant_id,
            MerchantShippingZone.id == id,
        )
        .first()
    )


def create_warehouse_for_shipping_zone(
    db: Session, *, merchant_id: str, shipping_zone_id: str, saleor_warehouse_id: str
) -> MerchantWarehouse:
    """
    creates warehouse for shipping zone
    """
    shipping_zone = (
        db.query(MerchantShippingZone)
        .filter(
            MerchantShippingZone.id == shipping_zone_id,
            MerchantShippingZone.merchant_id == merchant_id,
        )
        .first()
    )
    if not shipping_zone:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shipping zone not found",
        )
    new_warehouse = MerchantWarehouse(
        saleor_warehouse_id=saleor_warehouse_id,
        merchant_id=merchant_id,
        shipping_zone=shipping_zone,
    )

    db.add(new_warehouse)
    db.commit()
    db.refresh(new_warehouse)
    db.refresh(shipping_zone)

    return new_warehouse


def get_merchant_warehouse_by_id(
    db: Session, *, merchant_id: str, id: str
) -> MerchantWarehouse | None:
    """
    Get a merchant warehouse by id for a specific merchant.
    """
    return (
        db.query(MerchantWarehouse)
        .filter(
            MerchantWarehouse.merchant_id == merchant_id, MerchantWarehouse.id == id
        )
        .first()
    )


def create_db_merchant_warehouse(
    db: Session, *, merchant_id: str, saleor_warehouse_id: str, address_id: str
) -> MerchantWarehouse:
    """
    creates warehouse for shipping zone
    """
    new_warehouse = MerchantWarehouse(
        saleor_warehouse_id=saleor_warehouse_id, merchant_id=merchant_id, address_id=address_id
    )

    db.add(new_warehouse)
    db.commit()
    db.refresh(new_warehouse)

    return new_warehouse


def list_merchant_warehouses(
    db: Session, *, merchant_id: str
) -> List[MerchantWarehouse]:
    """
    Get a merchant by ID.
    """
    return (
        db.query(MerchantWarehouse)
        .filter(MerchantWarehouse.merchant_id == merchant_id)
        .all()
    )


def get_airlinks_by_merchant_bin(
    db: Session, *, merchant_bin: str
) -> list[Airlink] | list:
    """
    Get airlinks by merchant bin.
    """
    return (
        db.query(Airlink)
        .join(Airlink.merchant)
        .filter(Merchant.bin == merchant_bin)
        .all()
    )


def get_employees_query_for_merchant(
    db: Session, *, merchant: Merchant
) -> Query:
    """Returns a query for employees associated with the given merchant."""
    return (
        db.query(User)
        .join(User.merchants)
        .filter(Merchant.id == merchant.id)
        .order_by(User.id)
    )


def get_employees_for_merchant(
    db: Session, *, merchant: Merchant
) -> List[User]:
    """Returns a list of employees associated with the given merchant."""
    return get_employees_query_for_merchant(db, merchant=merchant).all()


def create_employee_for_merchant(
    db: Session, *, merchant: Merchant, employee: EmployeeProfile
) -> EmployeeProfile:
    """Creates employee for merchant"""

    db_employee = employee
    db.add(db_employee)
    db.flush()
    db.refresh(db_employee)

    # The `employees` relationship on Merchant is with the `User` model.
    # We need to append the `User` object associated with the `EmployeeProfile`.
    # The `db_employee.user` attribute is lazy-loaded by SQLAlchemy here.
    merchant.employees.append(db_employee.user)
    db.add(merchant)
    db.flush()
    db.refresh(merchant)

    return db_employee

async def create_employee_for_merchant_async(
        db: AsyncSession, *, merchant: Merchant, employee: EmployeeProfile
) -> EmployeeProfile:
    db_employee = employee
    db.add(db_employee)
    await db.flush()
    await db.refresh(db_employee)

    user = await db.get(User, db_employee.user_id)
    if not user:
        raise ValueError(f"User with id {db_employee.user_id} not found for employee profile.")

    # To prevent a lazy load on the `merchant.employees` collection, which
    # would cause a MissingGreenlet error in an async context, we need to
    # eagerly load it. We can do this by refreshing the merchant instance
    # and specifying the relationship to load.
    await db.refresh(merchant, attribute_names=["employees"])

    merchant.employees.append(user)
    db.add(merchant)
    await db.flush()

    return db_employee
