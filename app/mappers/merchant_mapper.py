from app.models.internal_model import Merchant
from app.schemas.integrations import MerchantOnboardRequest


def map_merchant_to_onboard_request(merchant: Merchant) -> MerchantOnboardRequest:
    """Mapping SQLAlchemy Merchant → MerchantOnboardRequest schema"""
    return MerchantOnboardRequest(
        name=merchant.legal_name,
        bin=merchant.bin,
        bank_account=merchant.iban,
        phone=str(merchant.phone),
        company_id=str(merchant.company_id),
        company_type=str(merchant.company_type),
        registration_date=str(merchant.registration_date),
        employee=None
    )