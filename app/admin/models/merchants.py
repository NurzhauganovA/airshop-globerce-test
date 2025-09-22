from sqladmin.filters import BooleanFilter

from app.admin.models.base import BaseAdmin
from app.models.internal_model import Merchant


class MerchantAdmin(BaseAdmin, model=Merchant):
    name = "Мерчант"
    name_plural = "Мерчанты"

    column_searchable_list = (
        Merchant.legal_name,
        Merchant.bin,
    )

    column_sortable_list = (
        Merchant.legal_name,
        Merchant.is_active,
        Merchant.created_at,
        Merchant.updated_at,
    )

    column_filters = (BooleanFilter(Merchant.is_active),)
