from typing import Optional

import xmltodict
from httpx import AsyncClient

from app.core.config import settings
from app.schemas.freedom import FPayCardPaymentRequestDto
import base64
import os
from typing import Dict, Any

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding
import hashlib
from collections import OrderedDict
from typing import List


pay_path = settings.FREEDOM_PAY_INIT_PAY
status_path = settings.FREEDOM_PAY_STATUS
terminal_registration_uri = settings.FREEDOM_PAY_TERMINAL_REGISTRATION_URI
terminal_registration_host = settings.FREEDOM_PAY_HOST
terminal_registration_token = settings.FREEDOM_PAY_TERMINAL_REGISTRATION_TOKEN
testMode = settings.FREEDOM_PAY_TEST_MODE


def generate_signature(
    request: Dict[str, Any],
    path: Optional[str] = None,
    skip_trim: Optional[bool] = False,
    secret_key: Optional[str] = None,
    test_mode=None,
) -> str:
    """
    Генерирует подпись для запроса в формате FreedomPay

    Args:
        request: словарь с данными запроса
        path: путь API (добавляется в начало)
        secret_key: секретный ключ (добавляется в конец)
        test_mode: режим тестирования

    Returns:
        MD5 подпись
    """
    request["pg_testing_mode"] = (
        1 if str(test_mode).lower() in ("true", "1", "yes", "y") else 0
    )

    flat_params = _make_flat_params_array(request)
    sorted_params = OrderedDict(sorted(flat_params.items()))

    values_for_signature = list(sorted_params.values())

    if path and skip_trim:
        values_for_signature.insert(0, path.lstrip("/"))
    if path and not skip_trim:
        values_for_signature.insert(0, path)
    if secret_key:
        values_for_signature.append(secret_key)

    signature = _generate_signature(values_for_signature)

    request["pg_sig"] = signature

    return signature


def _make_flat_params_array(
    params: Dict[str, Any], parent_name: str = ""
) -> Dict[str, str]:
    """Преобразует вложенные структуры в плоский словарь"""
    flat_params = {}
    idx = 0

    for key, value in params.items():
        idx += 1
        new_key = f"{parent_name}{key}{idx:03d}"

        if isinstance(value, dict):
            flat_params.update(_make_flat_params_array(value, new_key))
        elif isinstance(value, list):
            for j, item in enumerate(value):
                list_key = f"{new_key}{(j + 1):03d}"
                if isinstance(item, (dict, list)):
                    flat_params.update(_make_flat_params_array({list_key: item}))
                else:
                    flat_params[list_key] = str(item) if item is not None else ""
        else:
            if value is not None:
                flat_params[new_key] = str(value)

    return flat_params


def _generate_signature(values: List[str]) -> str:
    """Генерирует MD5 подпись из списка значений"""
    concatenated_string = ";".join(values)
    return hashlib.md5(concatenated_string.encode("utf-8")).hexdigest()


class RSADecryption:
    PRIVATE_KEY_PATH = settings.FREEDOM_PAY_PRIVATE_KEY_PEM_PATH

    @staticmethod
    def decrypt(encrypted_text: str) -> str:
        if not encrypted_text:
            raise ValueError("Encrypted text cannot be empty")

        try:
            private_key = RSADecryption.load_private_key()
            encrypted_bytes = base64.b64decode(encrypted_text)

            decrypted_bytes = private_key.decrypt(encrypted_bytes, padding.PKCS1v15())
            return decrypted_bytes.decode("utf-8")

        except Exception as e:
            raise RuntimeError("Failed to decrypt the secret key") from e

    @staticmethod
    def load_private_key():
        """Загрузка приватного ключа из PEM файла"""

        if not os.path.exists(RSADecryption.PRIVATE_KEY_PATH):
            BASE_DIR = os.path.dirname(
                os.path.abspath(__file__)
            )  # папка текущего скрипта
            key_path = os.path.join(BASE_DIR, "keys", "private.pem")
            print("if")
        else:
            key_path = RSADecryption.PRIVATE_KEY_PATH
            print("else")

        with open(key_path, "rb") as key_file:
            private_key = serialization.load_pem_private_key(
                key_file.read(), password=None, backend=default_backend()
            )
        return private_key

    @staticmethod
    def create_request_params(
        request_params: Dict[str, Any],
        path: str,
        decrypted_secret_key: str,
        is_test_mode: bool = False,
    ) -> Dict[str, Any]:
        """
        Генерация финальных параметров для FreedomPay запроса с подписью.
        """

        return request_params


class FreedomPayService:
    """
    service provides integration with freedomPay.
    """

    def __init__(self, url: str, token: str):
        self.base_url = url.rstrip("/")
        self.client = AsyncClient(
            base_url=url, headers={"Authorization": f"Bearer {token}"}
        )

    async def register_terminal(self) -> Optional[dict]:
        """Send payment request to FreedomPay API"""
        try:
            response = await self.client.post(pay_path)
            response.raise_for_status()
            return xmltodict.parse(response.text)

        except Exception as e:
            print(f"Payment error: {e}")
            return None

    async def pay(self, data: FPayCardPaymentRequestDto) -> Optional[dict]:
        """Send payment request to FreedomPay API"""
        try:
            decrypted = RSADecryption.decrypt(data.secret_key)
            data = data.to_form_data()
            generate_signature(
                request=data, path=pay_path, secret_key=decrypted, test_mode=testMode
            )

            response = await self.client.post(pay_path, data=data)
            response.raise_for_status()
            return xmltodict.parse(response.text)

        except Exception as e:
            print(f"Payment error: {e}")
            return None

    async def get_status(self, data: FPayCardPaymentRequestDto) -> Optional[dict]:
        """Send status request to FreedomPay API"""
        try:
            decrypted = RSADecryption.decrypt(data.secret_key)
            data = data.to_form_data()
            generate_signature(
                request=data,
                path="status_v2",
                skip_trim=True,
                secret_key=decrypted,
                test_mode=testMode,
            )
            print(data)

            response = await self.client.post(status_path, data=data)
            response.raise_for_status()
            return xmltodict.parse(response.text)

        except Exception as e:
            print(f"Get status error: {e}")
            return None

    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()
