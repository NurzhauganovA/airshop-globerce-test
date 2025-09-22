# app/schemas/notification_schemas.py

from typing import Optional, Dict, List
from uuid import UUID

from pydantic import BaseModel, Field
from enum import Enum


class NotificationType(str, Enum):
    sms = "sms"
    push = "push"
    email = "email"


class NotificationStatus(str, Enum):
    queued = "queued"
    sent = "sent"
    failed = "failed"


# --- Templates ---
class TemplateCreate(BaseModel):
    name: str = Field(..., max_length=100)
    purpose: str = Field(..., max_length=100)
    type: NotificationType = NotificationType.sms
    content: str = Field(..., max_length=150)
    # для push
    title: Optional[str] = None

class TemplateOut(BaseModel):
    id: str
    name: str
    purpose: Optional[str] = None
    type: NotificationType


class SmsTemplateOut(BaseModel):
    id: str
    template_id: str
    content: str


class TemplateWithSmsOut(TemplateOut):
    sms: Optional[SmsTemplateOut] = None


class TemplateList(BaseModel):
    items: List[TemplateOut]
    total: int


class TemplatePatch(BaseModel):
    name: Optional[str] = None
    content: Optional[str] = None
    type: Optional[NotificationType] = None


# --- Send SMS ---
class SmsSendByRequest(BaseModel):
    phone: str
    params: Dict[str, str] = {}


class SmsSendResponse(BaseModel):
    id: str
    status: NotificationStatus
    phone: str

# --- Send PUSH ---
class PushSendByRequest(BaseModel):
    recipient_id: UUID
    # Если в шаблоне есть плейсхолдеры (%s)
    title_params: List[str] = Field(default_factory=list)
    content_params: List[str] = Field(default_factory=list)

class PushSendResponse(BaseModel):
    id: str
    status: NotificationStatus
    recipient_id: str