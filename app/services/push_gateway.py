# app/services/push_gateway.py

import uuid
import logging
from typing import Tuple, Dict, Optional

import httpx
from app.core.config import settings

log = logging.getLogger(__name__)

class PushTrafficClient:

    def __init__(self):
        self.url: str = settings.PUSH_API_URL
        self.api_key: str = settings.PUSH_API_KEY
        self.category: str = settings.PUSH_CATEGORY
        self.api_key_header: str = settings.PUSH_API_KEY_HEADER
        self.timeout: float = settings.PUSH_TIMEOUT_SEC

    async def _post(self, payload: dict, headers: Dict[str, str]) -> httpx.Response:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(self.url, json=payload, headers=headers)
            return resp

    async def send(self, *, recipient_id: str, content: str, title: Optional[str] = None) -> Tuple[bool, Dict]:
        """
        Возвращает (ok, info). ok = True при HTTP 200. info — тело ответа/диагностика.
        """
        if not recipient_id:
            raise ValueError("recipient_id обязателен")
        if not content or not content.strip():
            raise ValueError("content обязателен")

        request_id = str(uuid.uuid4())

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            self.api_key_header: self.api_key,
            "X-Request-Id": request_id,
        }

        payload = {
            "recipient": recipient_id,
            "type": "PUSH",
            "dataMap": {
                "body": content.strip(),
                "category": self.category,
            },
        }
        if title and title.strip():
            payload["dataMap"]["title"] = title.strip()

        try:
            resp = await self._post(payload, headers)
        except httpx.RequestError as e:
            msg = f"Push HTTP error [{request_id}]: {e}"
            log.warning(msg)
            return False, {"error": "request_error", "message": msg}

        ok = resp.status_code == 200
        info: Dict = {"status_code": resp.status_code}

        try:
            info["json"] = resp.json()
        except ValueError:
            info["text"] = resp.text

        level = logging.INFO if ok else logging.WARNING
        log.log(level, "Push reply [%s]: %s", request_id, info)

        return ok, info