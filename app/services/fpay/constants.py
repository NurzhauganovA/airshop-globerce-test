from app.core.config import settings


class FreedomP2PConstants:
    FREEDOM_P2P_INIT_PAYMENT_TOKEN = settings.FREEDOM_P2P_INIT_PAYMENT_TOKEN
    FREEDOM_P2P_CONFIRM_PAYMENT_TOKEN = settings.FREEDOM_P2P_CONFIRM_PAYMENT_TOKEN
    FREEDOM_P2P_BASE_URL = settings.FREEDOM_P2P_BASE_URL
    FREEDOM_P2P_INIT_PAYMENT_URL = settings.FREEDOM_P2P_INIT_PAYMENT_URL
    FREEDOM_P2P_CONFIRM_PAYMENT_URL = settings.FREEDOM_P2P_CONFIRM_PAYMENT_URL

    @classmethod
    def init_payment_url(cls) -> str:
        return cls._join(cls.FREEDOM_P2P_BASE_URL, cls.FREEDOM_P2P_INIT_PAYMENT_URL)

    @classmethod
    def confirm_payment_url(cls) -> str:
        return cls._join(cls.FREEDOM_P2P_BASE_URL, cls.FREEDOM_P2P_INIT_PAYMENT_URL)

    @staticmethod
    def _join(base: str, path: str) -> str:
        return f"{base.rstrip('/')}/{path.lstrip('/')}"


class FreedomP2PPaymentStatuses:
    HOLD = "HOLD"
    CANCELLED = "CANCELLED"

    PAYMENT_STATUS_TO_TRANSACTION_STATUS_MAP = {
        HOLD: 'PAID',
        CANCELLED: 'CANCELLED',
    }


class FreedomP2PUnholdPaymentConstants:
    SUCCESS = "SUCCESS"
    ERROR = "ERROR"
    SUCCESS_ERROR_MSG = "Платеж с референсом обработан"
