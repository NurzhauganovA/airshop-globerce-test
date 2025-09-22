# app/controllers/internal_controller.py

import uuid
from typing import Optional, List

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.controllers.base import BaseController
from app.core import security
from app.models.internal_model import Customer, User, Address, City, Country
from app.schemas.auth_schemas import OTPSendRequest


class UserController(BaseController[User, OTPSendRequest, OTPSendRequest]):
    """
    Controller for handling User model operations.
    """

    def get_by_phone(self, db: Session, *, phone_number: str) -> Optional[User]:
        """
        Retrieves a user by their unique phone number.
        """
        return (
            db.query(self._model)
            .filter(self._model.phone_number == phone_number)
            .first()
        )

    def get_by_username(self, db: Session, *, username: str) -> Optional[User]:
        """
        Retrieves a user by their username.
        """
        return db.query(self._model).filter(self._model.username == username).first()

    def get_by_username_or_phone(self, db: Session, *, user_credential: str):
        return (
            db.query(self._model)
            .filter(
                or_(
                    self._model.username == user_credential,
                    self._model.phone_number == user_credential,
                )
            )
            .first()
        )

    def create_with_phone(
        self, db: Session, *, phone_number: str, **extra_fields
    ) -> User:
        """
        Creates a new user with a phone number.
        A dummy password is created as it's a required field.
        This method does NOT commit the session.
        """
        dummy_password_hash = security.get_password_hash(str(uuid.uuid4()))
        db_user = User(
            phone_number=phone_number, password_hash=dummy_password_hash, **extra_fields
        )
        db.add(db_user)
        db.flush()  # Ensure the object has an ID before refreshing
        db.refresh(db_user)
        return db_user


# Instantiate the controller classes to be used in your API endpoints
user_controller = UserController(User)


class CustomerController(BaseController[Customer, OTPSendRequest, OTPSendRequest]):
    """
    Controller for handling Customer model operations.
    """

    def create_from_user(self, db: Session, *, user: User) -> Customer:
        """
        Creates a new Customer profile linked to an existing User.
        This method does NOT commit the session.
        """
        # Create a new Customer profile and link it to the user.
        db_customer = Customer(user_id=user.id)
        db.add(db_customer)
        return db_customer

    def get_by_customer_id(
        self, db: Session, *, customer_id: str
    ) -> Optional[Customer]:
        db_customer = (
            db.query(self._model).filter(self._model.id == customer_id).first()
        )
        return db_customer

    def get_by_user_id(self, db: Session, *, user_id: str) -> Optional[Customer]:
        db_customer = (
            db.query(self._model).filter(self._model.user_id == user_id).first()
        )
        return db_customer

    def get_addresses_by_user_id(
        self, db: Session, *, user_id: str
    ) -> List[Optional[Address]]:
        db_customer = (
            db.query(self._model).filter(self._model.user_id == user_id).first()
        )
        return db_customer.delivery_addresses if db_customer else []

    def create_delivery_address(
        self, db: Session, *, customer_id: str, address: Address
    ) -> Address:
        db_customer = (
            db.query(self._model).filter(self._model.id == customer_id).first()
        )
        if not db_customer:
            raise ValueError("Customer not found")
        db_address = Address(**address.dict())
        db_customer.delivery_addresses.append(db_address)
        db.commit()
        db.refresh(db_address)
        return db_address

    def get_address_by_id(
        self, db: Session, *, address_id: str, customer_id: str
    ) -> Optional[Address]:
        db_address = (
            db.query(Address)
            .join(Address.delivery_for_customers)
            .filter(Address.id == address_id, Customer.id == customer_id)
            .first()
        )
        return db_address


customer_controller = CustomerController(Customer)


class AddressController(BaseController[Address, City, Country]):
    """
    Controller for handling Address model operations.
    """

    def list_all(self, db: Session) -> List:
        return db.query(self._model).all()

    def get_address_by_id(self, db: Session, *, address_id: str) -> Optional[Address]:
        return db.query(self._model).filter(self._model.id == address_id).first()

    def get_city_by_id(self, db: Session, *, city_id: str) -> Optional[City]:
        return db.query(City).filter(City.id == city_id).first()

    def get_all_addresses_by_user_id(
        self, db: Session, user_id: str, as_query: bool = False
    ):
        query = (
            db.query(self._model)
            .join(self._model.delivery_for_customers)
            .join(Customer.user)
            .filter(User.id == user_id)
        )
        if as_query:
            return query

        return query.all()
    
    def create_address(self, db: Session, *, address: Address) -> Address:
        db_address = Address(**address)
        db.add(db_address)
        db.commit()
        db.refresh(db_address)
        return db_address




class CityController(AddressController):
    def get_cursor_query(self, db: Session, base_query=None):
        return db.query(self._model).order_by(self._model.id)


class CountryController(CityController): ...


address_controller = AddressController(Address)
city_controller = CityController(City)
country_controller = CountryController(Country)
