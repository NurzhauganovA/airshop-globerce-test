import os

import httpx
import asyncio
import time
from typing import Optional, Dict, Any

from dataclasses import dataclass


@dataclass
class AsyncJWTTokenManager:
    auth_url: str
    auth_credentials: Dict[str, Any]
    token_ttl: int = 3600

    def __post_init__(self):
        self._token: Optional[str] = None
        self._expiry_time: float = 0
        self._lock = asyncio.Lock()
        self._client: Optional[httpx.AsyncClient] = None

    async def get_token(self) -> str:
        """Асинхронно получить валидный токен"""
        async with self._lock:
            if self._is_token_expired():
                await self._refresh_token()
            return self._token

    def _is_token_expired(self) -> bool:
        return time.time() >= self._expiry_time or self._token is None

    async def _refresh_token(self):
        """Асинхронно обновить токен с помощью httpx"""
        try:
            print("Refreshing token...")
            if self._client is None:
                self._client = httpx.AsyncClient(timeout=10.0)

            response = await self._client.post(
                self.auth_url, json=self.auth_credentials
            )
            response.raise_for_status()

            token_data = response.json()
            self._token = token_data["access"]
            self._expiry_time = time.time() + self.token_ttl

        except httpx.RequestError as e:
            raise Exception(f"Failed to get JWT token: {e}")
        except httpx.HTTPStatusError as e:
            raise Exception(f"Auth API returned error: {e.response.status_code}")

    async def close(self):
        """Закрыть клиент"""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


auth_url = os.getenv("FREEDOM_MFO_AUTH_URL", "http://localhost:8080/ffc-api-auth")
token_manager = AsyncJWTTokenManager(
    auth_url,
    auth_credentials={
        "username": os.getenv("FREEDOM_MFO_USERNAME", "admin"),
        "password": os.getenv("FREEDOM_MFO_PASSWORD", ""),
    },
    token_ttl=3600,
)
