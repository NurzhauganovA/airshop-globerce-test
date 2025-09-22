from pydantic import BaseModel, Field
from typing import Optional, List, Any

from app.models.internal_model import Merchant, User


class SimpleMerchantSchema(BaseModel):
    id: str
    legal_name: str
    bin: str

    @classmethod
    def from_model(cls, merchant: Merchant) -> "SimpleMerchantSchema":
        """Создает схему из модели Merchant"""
        return cls(
            id=str(merchant.id), legal_name=merchant.legal_name, bin=merchant.bin
        )


class SimpleUserSchema(BaseModel):
    id: str
    email: Optional[str] = None
    phone_number: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    username: Optional[str] = None
    is_merchant: bool
    is_admin: bool
    is_technical: bool
    created_at: Any
    updated_at: Any

    @classmethod
    def from_model(cls, user: User) -> "SimpleUserSchema":
        """Создает схему из модели User"""
        return cls(
            id=str(user.id),
            email=user.email,
            phone_number=user.phone_number,
            username=user.username,
            is_merchant=user.is_merchant,
            is_admin=user.is_admin,
            is_technical=user.is_technical,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )


class BaseEmployeeSchema(BaseModel):
    user: SimpleUserSchema
    merchants: List[SimpleMerchantSchema]

    @classmethod
    def from_model(cls, user: User) -> "BaseEmployeeSchema":
        """Создает схему из модели User"""
        user_schema = SimpleUserSchema.from_model(user)

        merchant_schemas = [
            SimpleMerchantSchema.from_model(merchant) for merchant in user.merchants
        ]

        return cls(user=user_schema, merchants=merchant_schemas)


class EmployeeListSchema(BaseModel):
    employees: List[BaseEmployeeSchema]

    @classmethod
    def from_models(cls, users: List[User]) -> "EmployeeListSchema":
        """Создает схему из списка моделей User"""
        employee_schemas = [BaseEmployeeSchema.from_model(user) for user in users]

        return cls(employees=employee_schemas)


class EmployeeSimpleAddSchema(BaseModel):
    phone: str = Field(..., pattern=r"^7[0-9]{10}$")
    first_name: str
    last_name: str
    email: Optional[str] = None
