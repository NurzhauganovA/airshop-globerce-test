import httpx
from dataclasses import dataclass
from typing import Any
from app.core.config import settings


@dataclass
class IBCCUserResponse:
    companies: Any
    company: Any  # Represents CompanyDto in Java
    user: Any  # Represents UserDto in Java


@dataclass
class IBCCTokenResponse:
    accessToken: str
    # Add other fields like token_type, expires_in, etc.


@dataclass
class IBCCTokenRequest:
    clientId: str
    clientSecret: str
    scope: str
    cas: str
    grant_type: str = "password"


# Constants from the Java code
HEADER_DEVICE_ID = "X-Device-Id"
AUTHORIZATION = "Authorization"
FILTER_PARAM = "filter"


# --- Main Service Class ---
class IBCCAuthService:
    """
    IBCCAuthService.

    This class provides the authentication logic for the IBCC API, translated from Java.
    It uses asyncio for a non-blocking, async flow.
    """

    def __init__(
        self,
        client_id: str = settings.IBCC_AUTH_CLIENT_ID,
        client_secret: str = settings.IBCC_AUTH_CLIENT_SECRET,
        scope: str = "cas",
        auth_url: str = settings.IBCC_AUTH_URL,
        user_url: str = settings.IBCC_USER_AUTH_URL,
        device_id: str = settings.IBCC_USER_DEVICE_ID,
    ):
        """
        Initializes the service with its dependencies.
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.scope = scope
        self.auth_url = auth_url
        self.user_url = user_url
        self.device_id = device_id

    async def _get_token(self, cas: str) -> IBCCTokenResponse:
        token_request = IBCCTokenRequest(
            clientId=self.client_id,
            clientSecret=self.client_secret,
            cas=cas,
            scope=self.scope,
        )
        try:
            async with httpx.AsyncClient() as client:
                token_response = await client.post(
                    url=self.auth_url, json=token_request.__dict__, timeout=15
                )
            token_response.raise_for_status()
            return token_response.json()
        except httpx.HTTPError as e:
            print(f"Error during auth {e}")

    async def _get_ibcc_user(self, cas: str) -> IBCCUserResponse:
        try:
            token_data = await self._get_token(cas)
            if not token_data:
                return None
            headers = {
                HEADER_DEVICE_ID: self.device_id,
                AUTHORIZATION: f"Bearer {token_data['accessToken']}",
            }
            async with httpx.AsyncClient() as client:
                user_response = await client.get(
                    url=self.user_url, headers=headers, timeout=15
                )
            user_response.raise_for_status()
            return user_response.json()
        except httpx.HTTPError as e:
            print(f"Error during get_ibcc_user {e}")
        except (KeyError, TypeError) as e:
            print(f"Error processing token response in _get_ibcc_user: {e}")
