import datetime
import enum
import uuid
from sqlalchemy import (
    Column,
    String,
    Text,
    Enum,
    DateTime,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base


class NotificationType(str, enum.Enum):
    sms = "sms"
    push = "push"
    email = "email"


class NotificationStatus(str, enum.Enum):
    queued = "queued"
    sent = "sent"
    failed = "failed"


class Template(Base):
    __tablename__ = "template"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False, unique=True)
    purpose = Column(String(100), nullable=False, unique=True)
    type = Column(Enum(NotificationType, name="template_type"), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.now(datetime.timezone.utc))
    updated_at = Column(
        DateTime,
        default=datetime.datetime.now(datetime.timezone.utc),
        onupdate=datetime.datetime.now(datetime.timezone.utc),
    )

    sms_template = relationship("SmsTemplate", back_populates="template", uselist=False)
    push_template = relationship("PushTemplate", back_populates="template", uselist=False)
    notifications = relationship("Notification", back_populates="template")


class SmsTemplate(Base):
    __tablename__ = "sms_template"
    __table_args__ = (
        UniqueConstraint("template_id", name="uq_sms_template_template_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    template_id = Column(
        UUID(as_uuid=True),
        ForeignKey("template.id", ondelete="CASCADE"),
        nullable=False,
    )
    content = Column(Text, nullable=False)

    template = relationship("Template", back_populates="sms_template")


class Notification(Base):
    __tablename__ = "notification"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    template_id = Column(
        UUID(as_uuid=True),
        ForeignKey("template.id", ondelete="SET NULL"),
        nullable=True,
    )
    type = Column(Enum(NotificationType, name="notification_type"), nullable=False)
    status = Column(
        Enum(NotificationStatus, name="notification_status"),
        nullable=False,
        default=NotificationStatus.queued,
    )
    created_at = Column(DateTime, default=datetime.datetime.now(datetime.timezone.utc))
    updated_at = Column(
        DateTime,
        default=datetime.datetime.now(datetime.timezone.utc),
        onupdate=datetime.datetime.now(datetime.timezone.utc),
    )

    template = relationship("Template", back_populates="notifications")
    sms = relationship("SmsNotification", back_populates="notification", uselist=False)
    push = relationship("PushNotification", back_populates="notification", uselist=False)

class SmsNotification(Base):
    __tablename__ = "sms_notification"
    __table_args__ = (
        UniqueConstraint("notification_id", name="uq_sms_notification_notification_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    notification_id = Column(
        UUID(as_uuid=True),
        ForeignKey("notification.id", ondelete="CASCADE"),
        nullable=False,
    )
    phone = Column(String(32), nullable=False)
    message = Column(Text, nullable=False)

    notification = relationship("Notification", back_populates="sms")


class PushTemplate(Base):
    __tablename__ = "push_template"
    __table_args__ = (
        UniqueConstraint("template_id", name="uq_push_template_template_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    template_id = Column(UUID(as_uuid=True), ForeignKey("template.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)

    template = relationship("Template", back_populates="push_template")

class PushNotification(Base):
    __tablename__ = "push_notification"
    __table_args__ = (
        UniqueConstraint("notification_id", name="uq_push_notification_notification_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    notification_id = Column(UUID(as_uuid=True), ForeignKey("notification.id", ondelete="CASCADE"), nullable=False)
    recipient_id = Column(UUID(as_uuid=True), nullable=False)
    title = Column(String(255), nullable=False)
    body = Column(Text, nullable=False)

    notification = relationship("Notification", back_populates="push")

