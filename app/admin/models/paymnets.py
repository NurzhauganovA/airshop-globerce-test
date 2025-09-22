from sqladmin.filters import BooleanFilter

from app.admin.models.base import BaseAdmin
from app.models.internal_model import BasePaymentMethod


class BasePaymentMethodAdmin(BaseAdmin, model=BasePaymentMethod):
    name = "Базовый способ оплаты"
    name_plural = "Базовые способы оплаты"

    column_searchable_list = (
        BasePaymentMethod.type,
        BasePaymentMethod.loan_type,
    )

    column_sortable_list = (
        BasePaymentMethod.type,
        BasePaymentMethod.loan_type,
        BasePaymentMethod.enabled,
    )

    column_filters = (BooleanFilter(BasePaymentMethod.enabled),)
