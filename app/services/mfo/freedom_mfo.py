from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic.types import UUID


from app.core.config import settings
from pydantic import BaseModel, field_serializer
from app.services.mfo.AsyncAPIClient import AsyncAPIClient
import httpx

path = settings.FREEDOM_MFO_REGISTRATION_URL
period_url = settings.FREEDOM_MFO_PERIOD_URL
account_organization = settings.FREEDOM_MFO_ACCOUNT_ORGANIZATION
account_bik = settings.FREEDOM_MFO_ACCOUNT_BIK
kbe: int = int(settings.FREEDOM_MFO_KBE)
enterprise_type = settings.FREEDOM_MFO_ENTERPRISE_TYPE
contract_code = settings.FREEDOM_MFO_CONTRACT_CODE


class StoreRegistrationRequest(BaseModel):
    partner_id: Optional[str] = None
    name: Optional[str] = None
    contract_code: Optional[str] = None
    enterprise_type: Optional[str] = None
    bin: Optional[str] = None
    kbe: Optional[int] = None
    account_bik: Optional[str] = None
    account: Optional[str] = None
    account_organization: Optional[str] = None
    phone: Optional[str] = None
    registration_date: Optional[str] = None


class AdditionalInformationSchema(BaseModel):
    reference_id: Optional[str] = None
    success_url: Optional[str] = None
    failure_url: Optional[str] = None
    hook_url: Optional[str] = None
    seller_phone: Optional[str] = None


class GoodsSchema(BaseModel):
    cost: float
    quantity: int
    category: str


class ApplyLoanRequest(BaseModel):
    iin: str
    mobile_phone: str
    product: str
    partner: str
    channel: str
    credit_params: Dict[str, Any]
    additional_information: AdditionalInformationSchema
    extract_files_list: Optional[List[str]] = None
    merchant: Dict[str, Any]
    credit_goods: List[GoodsSchema]


class SendOTPRequest(BaseModel):
    phone: str
    iin: str


class ValidateOTPRequest(BaseModel):
    phone: str
    iin: str
    code: str


class CreditParams(BaseModel):
    period: int
    principal: float


class PickOfferSchema(BaseModel):
    credit_params: CreditParams
    product: str
    reference_id: UUID

    @field_serializer("reference_id")
    def serialize_uuid(self, reference_id: UUID) -> str:
        return str(reference_id)


class FreedomMfoService:
    """
    service provides integration with freedom mfo.
    """

    def __init__(self, url: str):
        self.client = AsyncAPIClient(base_url=url)

    async def _get_auth_token(self) -> str:
        print("Making Auth")
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url=f"{settings.FREEDOM_MFO_AUTH_URL}",
                json={
                    "username": settings.FREEDOM_MFO_USERNAME,
                    "password": settings.FREEDOM_MFO_PASSWORD,
                },
                timeout=30,
            )
        response.raise_for_status()

        if response.status_code != 200:
            print(response.json())
            raise ValueError("Failed to get auth token")

        access_token = response.json().get("access")

        return access_token

    async def register_merchant(self, bin, name, phone, account) -> Optional[dict]:
        """create partner"""
        try:
            request = StoreRegistrationRequest(
                partner_id=f"MP-{bin}",
                bin=bin,
                name=name,
                phone=phone,
                account=account,
                registration_date=datetime.now().isoformat(),
                account_bik=account_bik,
                account_organization=account_organization,
                kbe=kbe,
                enterprise_type=enterprise_type,
                contract_code=contract_code,
            )

            return await self.client.make_request(
                endpoint=path, method="POST", json=request.model_dump()
            )
        except Exception as e:
            print(f"Payment error: {e}")
            return None

    async def generate_periods(self, bin) -> Optional[dict]:
        try:
            return await self.client.make_request(
                endpoint=f"{period_url}{bin}", method="GET"
            )
        except Exception as e:
            print(f"Payment error: {e}")
            return None

    async def send_loan_request(self, request_data: ApplyLoanRequest):
        token = await self._get_auth_token()
        headers = {"Authorization": f"JWT {token}"}
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url=f"{settings.FREEDOM_MFO_HOST}{settings.FREEDOM_MFO_APPLY_URL}",
                    headers=headers,
                    json=request_data.model_dump(exclude_none=True),
                    timeout=30,
                )
            response.raise_for_status()
            return response

        except Exception as e:
            print(f"Send loan request error: {e}")
            raise

    async def send_otp(self, otp_data: SendOTPRequest):
        token = await self._get_auth_token()
        headers = {"Authorization": f"JWT {token}"}
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url=f"{settings.FREEDOM_MFO_HOST}{settings.FREEDOM_MFO_SEND_OTP_URL}",
                    headers=headers,
                    json={"mobile_phone": otp_data.phone, "iin": otp_data.iin},
                    timeout=30,
                )
                print(otp_data.model_dump())
            response.raise_for_status()
            return response
        except Exception as e:
            print(f"Send otp error: {e}")
            raise

    async def validate_otp(self, validate_data: ValidateOTPRequest):
        token = await self._get_auth_token()
        headers = {"Authorization": f"JWT {token}"}
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url=f"{settings.FREEDOM_MFO_HOST}{settings.FREEDOM_MFO_VALIDATE_OTP_URL}",
                    json={
                        "mobile_phone": validate_data.phone,
                        "iin": validate_data.iin,
                        "code": validate_data.code,
                    },
                    headers=headers,
                    timeout=30,
                )
            response.raise_for_status()
            return response
        except Exception as e:
            print(f"validate otp: {e}")
            raise

    async def get_offers(self, uuid: str):
        token = await self._get_auth_token()
        headers = {"Authorization": f"JWT {token}"}
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url=f"{settings.FREEDOM_MFO_HOST}{settings.FREEDOM_MFO_GET_STATUS}{uuid}",
                    headers=headers,
                    timeout=30,
                )
            response.raise_for_status()
            return response
        except Exception as e:
            print(f"get offers otp: {e}")
            raise

    async def set_offer(self, pick_offer_data: PickOfferSchema):
        token = await self._get_auth_token()
        headers = {"Authorization": f"JWT {token}"}
        try:
            async with httpx.AsyncClient() as client:
                response = await client.put(
                    url=f"{settings.FREEDOM_MFO_HOST}{settings.FREEDOM_MFO_SET_OFFER_URL}{pick_offer_data.reference_id}",
                    headers=headers,
                    json=pick_offer_data.model_dump(),
                    timeout=30,
                )
            response.raise_for_status()
            return response
        except Exception as e:
            print(f"get offers otp: {e}")
            raise

    async def close(self):
        """Close HTTP client"""
        await self.client.close()
