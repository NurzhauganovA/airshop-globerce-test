from typing import Optional

from httpx import AsyncClient

from app.core.config import settings

terminal_registration_uri = settings.FREEDOM_PAY_TERMINAL_REGISTRATION_URI
terminal_registration_host = settings.FREEDOM_PAY_HOST
terminal_registration_token = settings.FREEDOM_PAY_TERMINAL_REGISTRATION_TOKEN


class FreedomTerminalService:
    """
    service provides integration with freedomPay.
    """

    def __init__(self, url: str, token: str):
        self.base_url = url.rstrip("/")
        self.client = AsyncClient(
            base_url=url, headers={"Authorization": f"Bearer {token}"}
        )

    async def register_terminal(self, store_id: str) -> Optional[dict]:
        """Send payment request to FreedomPay API"""
        try:
            response = await self.client.post(
                f"{terminal_registration_uri}{store_id}",
                headers={
                    "Content-Type": "application/json",
                    "api-key": terminal_registration_token,
                },
            )
            response.raise_for_status()
            return response.json()
        # https://ibul.trafficwave.kz/merchant/v1/connect-acquiring/e03f11c1-6d65-44e0-b86c-77b9ab219111
        except Exception as e:
            print(f"Payment error: {e}")
            return None

    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()


freedom_terminal = FreedomTerminalService(
    terminal_registration_host, terminal_registration_token
)
