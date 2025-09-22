from pydantic import BaseModel, Field
from typing import Optional
from pydantic.types import NaiveDatetime
from app.models.internal_model import User, Customer




class CustomerProfile(BaseModel):
    first_name: Optional[str] = None
    surname: Optional[str] = None
    middle_name: Optional[str] = None
    default_locale: Optional[str] = Field(..., pattern="^(kk|ru|en)$")

    def to_db_model(self) -> Customer:
        """returns db model to saving"""

        return Customer(
            first_name = self.first_name,
            surname = self.surname,
            middle_name = self.middle_name,
            default_locale = self.default_locale
        )
    
    def update_db_model(self, db_model: Customer) -> Customer:
        """returns db model to saving"""
        db_model.first_name = self.first_name
        db_model.surname = self.surname
        db_model.middle_name = self.middle_name
        db_model.default_locale = self.default_locale

        return db_model

class EmployeeProfile(BaseModel):
    first_name: str
    last_name: str
    middle_name: Optional[str]


class UserProfileSchema(BaseModel):
    user_id: str
    is_merchant: bool
    phone_number: str
    email: Optional[str]
    created_at: NaiveDatetime
    updated_at: NaiveDatetime
    customer_profile: Optional[CustomerProfile]
    employee_profile: Optional[EmployeeProfile]

    @staticmethod
    def from_db_model(db_model):
        """Loads model from db model"""
        return UserProfileSchema(
            user_id = db_model.id,
            is_merchant = db_model.is_merchant,
            phone_number = db_model.phone_number,
            email = db_model.email,
            created_at = db_model.created_at,
            updated_at = db_model.updated_at,
            customer_profile = CustomerProfile(
                    first_name=db_model.customer_profile.first_name,
                    surname=db_model.customer_profile.surname,
                    middle_name=db_model.customer_profile.middle_name,
                    default_locale=db_model.customer_profile.default_locale,
                ) if db_model.customer_profile else None,
            employee_profile = EmployeeProfile(
                    first_name=db_model.employee_profile.first_name,
                    last_name=db_model.employee_profile.last_name,
                    middle_name=db_model.employee_profile.middle_name,
                ) if db_model.employee_profile else None,
        )
    
class UserProfileUpdateSchema(BaseModel):
    email: Optional[str]
    customer_profile: Optional[CustomerProfile]

    def update_db_model(self, db_model: User) -> User:
        """returns db model to saving"""
        db_model.email = self.email
        if db_model.customer_profile:
            db_model.customer_profile = self.customer_profile.update_db_model(db_model.customer_profile)
        else:
            db_model.customer_profile = self.customer_profile.to_db_model() if self.customer_profile else None

        return db_model
