# app/services/sms_notification.py

import httpx
import re
import logging

from xml.etree import ElementTree
from jinja2 import Template as JinjaTemplate
from typing import Tuple, Dict
from app.core.config import settings

log = logging.getLogger(__name__)


def render_content(content: str, params: Dict[str, str]) -> str:
    if "%s" in content and len(params) == 1:
        v = next(iter(params.values()))
        return content % v
    return JinjaTemplate(content).render(**params)


class SmsTrafficClient:
    def __init__(self):
        self.primary_url = settings.SMS_API_URL
        self.backup_url = (
            self.primary_url.replace("api.", "api2.")
            if "api." in self.primary_url
            else self.primary_url
        )
        self.login = settings.SMS_API_LOGIN
        self.password = settings.SMS_API_PASSWORD

    @staticmethod
    def _normalize_phone(phone: str) -> str:
        digits = re.sub(r"\D", "", str(phone))
        if len(digits) == 11 and digits.startswith("8"):
            digits = "7" + digits[1:]
        return digits  # провайдер ждёт без плюса

    async def _post(self, url: str, payload: dict) -> str:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(url, data=payload)
            r.raise_for_status()
            return r.text

    def _parse_reply(self, xml_text: str) -> Dict[str, str]:
        xml = ElementTree.fromstring(xml_text)
        result = (xml.findtext("result") or "").upper()
        code = int(xml.findtext("code") or 0)
        desc = xml.findtext("description") or ""
        sms_id_node = xml.find(".//message_info/sms_id")
        sms_id = sms_id_node.text if sms_id_node is not None else None
        return {"result": result, "code": code, "description": desc, "sms_id": sms_id}

    async def send(self, phone: str, message: str) -> Tuple[bool, dict]:
        provider_phone = self._normalize_phone(phone)
        payload = {
            "login": self.login,
            "password": self.password,
            "phones": provider_phone,
            "message": message,
            "rus": 5,
            "want_sms_ids": 1,
        }

        try:
            text = await self._post(self.primary_url, payload)
        except httpx.RequestError as e:
            log.warning("SmsTraffic primary failed: %s; retry via backup", e)
            text = await self._post(self.backup_url, payload)

        info = self._parse_reply(text)
        info["phone_sent"] = provider_phone
        ok = info["result"] == "OK" and info["code"] == 0

        level = logging.INFO if ok else logging.WARNING
        log.log(level, "SmsTraffic reply: %s", info)

        return ok, info

    async def account(self) -> Dict[str, str]:
        payload = {
            "login": self.login,
            "password": self.password,
            "operation": "account",
        }
        text = await self._post(self.primary_url, payload)
        xml = ElementTree.fromstring(text)
        return {"account": xml.findtext("account")}
