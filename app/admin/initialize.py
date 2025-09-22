from sqladmin import Admin

from app.admin.models.base import AdminAuth
from app.admin.models.merchants import MerchantAdmin
from app.admin.models.paymnets import BasePaymentMethodAdmin
from app.admin.models.users import UserAdmin
from app.controllers.internal import user_controller
from app.core.config import settings
from app.core.database import SessionLocal

_admin: Admin | None = None


def initialize_admin_page(app, engine):
    global _admin
    if _admin is not None:
        return

    admin = Admin(
        app=app,
        engine=engine,
        authentication_backend=AdminAuth(
            secret_key=settings.SECRET_KEY,
            session_factory=SessionLocal,
            user_controller=user_controller,
        ),
    )
    admin.add_view(MerchantAdmin)
    admin.add_view(BasePaymentMethodAdmin)
    admin.add_view(UserAdmin)

    _admin = admin
