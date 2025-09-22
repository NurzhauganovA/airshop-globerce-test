import httpx
from typing import Dict, Optional

from app.services.mfo.AsyncJWTTokenManager import token_manager


class AsyncAPIClient:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.token_manager = token_manager
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Получить или создать клиент"""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def _get_headers(self) -> Dict[str, str]:
        """Получить заголовки с актуальным токеном"""
        token = await self.token_manager.get_token()
        return {"Authorization": f"JWT {token}", "Content-Type": "application/json"}

    async def make_request(
        self, endpoint: str, method: str = "GET", **kwargs
    ) -> Optional[dict]:
        """Сделать авторизованный запрос"""
        client = await self._get_client()
        url = f"{self.base_url}{endpoint}"
        headers = await self._get_headers()

        try:
            response = await client.request(
                method=method, url=url, headers=headers, **kwargs
            )
            response.raise_for_status()
            return response

        except httpx.HTTPStatusError as e:
            raise e

    async def close(self):
        """Закрыть клиент"""
        if self._client:
            await self._client.aclose()
            self._client = None
