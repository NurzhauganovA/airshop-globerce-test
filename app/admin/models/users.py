from sqladmin.filters import BooleanFilter

from app.admin.models.base import BaseAdmin
from app.models.internal_model import User


class UserAdmin(BaseAdmin, model=User):
    name = "Пользователь"
    name_plural = "Пользователи"
    column_exclude_list = [
        "password_hash",
    ]

    column_searchable_list = (
        User.phone_number,
        User.username,
        User.email,
    )

    column_sortable_list = (
        User.username,
        User.email,
        User.created_at,
        User.updated_at,
    )

    column_filters = (
        BooleanFilter(User.is_merchant),
        BooleanFilter(User.is_admin),
        BooleanFilter(User.is_technical),
    )
