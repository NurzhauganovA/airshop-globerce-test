# app/controllers/notification_controller.py

from uuid import UUID
from typing import Callable, Dict
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from typing import Tuple, Optional, Sequence, Union
from app.models.notification_models import (
    Template,
    SmsTemplate,
    PushTemplate,
    Notification,
    SmsNotification,
    PushNotification,
    NotificationType,
    NotificationStatus,
)
from app.schemas.notification_schemas import TemplateCreate, TemplatePatch
from app.services.sms_notification import SmsTrafficClient
from app.services.push_gateway import PushTrafficClient


class TemplateController:
    def __init__(self, db: Session):
        self.db = db

    def create(self, data: TemplateCreate) -> Template:
        """
        Создаёт Template и связанный подтип (SMS/PUSH) в одной транзакции.
        Бросает ValueError при неверных данных, SQLAlchemyError — при проблемах БД.
        """
        self._validate(data)

        name = data.name.strip()
        purpose = data.purpose.strip()
        content = data.content.strip()
        title = (data.title or "").strip()

        tpl = Template(name=name, purpose=purpose, type=data.type)

        try:
            with self.db.begin():
                self.db.add(tpl)
                self.db.flush()

                # диспетчеризация по типу нотифки
                creator_map: Dict[NotificationType, Callable[[UUID, str, str], None]] = {
                    NotificationType.sms: self._create_sms,
                    NotificationType.push: self._create_push,
                }
                creator = creator_map[data.type]
                creator(tpl.id, content, title)

            creator(tpl.id, content, title)

            self.db.refresh(tpl)
            return tpl

        except SQLAlchemyError:
            raise


    def _validate(self, data: TemplateCreate) -> None:
        if not data.name or not data.name.strip():
            raise ValueError("Поле 'name' обязательно.")
        if not data.purpose or not data.purpose.strip():
            raise ValueError("Поле 'purpose' обязательно.")
        # content обязателен для всех типов
        if not data.content or not data.content.strip():
            raise ValueError("Поле 'content' обязательно.")
        # для push нужен title
        if data.type == NotificationType.push and (not data.title or not data.title.strip()):
            raise ValueError("Для PUSH-шаблона поле 'title' обязательно.")

    def _create_sms(self, tpl_id: UUID, content: str, _: str) -> None:
        self.db.add(SmsTemplate(template_id=tpl_id, content=content))

    def _create_push(self, tpl_id: UUID, content: str, title: str) -> None:
        self.db.add(PushTemplate(template_id=tpl_id, title=title, content=content))


    def get_by_name(self, name: str) -> Optional[Template]:
        return self.db.query(Template).filter(Template.name == name).first()

    def list(self, offset=0, limit=50):
        q = self.db.query(Template).order_by(Template.created_at.desc())
        return q.offset(offset).limit(limit).all(), q.count()

    def patch(self, name: str, patch: TemplatePatch) -> Optional[Template]:
        tpl = self.get_by_name(name)
        if not tpl:
            return None
        data = patch.model_dump(exclude_unset=True)
        if "name" in data:
            tpl.name = data["name"]
        if "type" in data:
            tpl.type = data["type"]
        if "content" in data:
            if tpl.type != NotificationType.sms:
                raise ValueError("content применим только к type=sms")
            if tpl.sms_template:
                tpl.sms_template.content = data["content"]
            else:
                self.db.add(SmsTemplate(template_id=tpl.id, content=data["content"]))
        self.db.commit()
        self.db.refresh(tpl)
        return tpl


class TemplateNotFoundError(ValueError):
    pass


class MultipleTemplatesError(ValueError):
    pass


class NotificationController:
    def __init__(self, db: Session, sms_client=None, push_client=None):
        self.db = db
        self.sms_client = sms_client or SmsTrafficClient()
        self.push_client = push_client or PushTrafficClient()

    @staticmethod
    def _fmt(text: str, *params) -> str:
        try:
            return text % params if params else text
        except Exception:
            return text

    # ---------- SMS ----------
    def _get_sms_template_by_purpose(self, purpose: str) -> Template:
        q = (self.db.query(Template)
             .options(joinedload(Template.sms_template))
             .filter(Template.type == NotificationType.sms,
                     Template.purpose == purpose))

        items: Sequence[Template] = q.all()
        if len(items) == 0:
            raise TemplateNotFoundError(f"No Sms Template for type=sms, purpose={purpose}")
        if len(items) > 1:
            raise MultipleTemplatesError(f"More than 1 Sms Template for type=sms, purpose={purpose}")
        tpl = items[0]
        if not tpl.sms_template:
            raise TemplateNotFoundError(f"Template '{tpl.name}' has no sms_template")
        return tpl

    async def send_sms_by_purpose(
        self, purpose: str, phone: str, *fmt_params: str
    ) -> Tuple[Notification, SmsNotification]:

        tpl = self._get_sms_template_by_purpose(purpose)
        content_template = tpl.sms_template.content

        message = self._fmt(content_template, *fmt_params)

        notif = Notification(
            template_id=tpl.id,
            type=NotificationType.sms,
            status=NotificationStatus.queued,
        )
        sms_notif = SmsNotification(notification_id=None, phone=phone, message=message)

        try:
            self.db.add(notif)
            self.db.flush()
            sms_notif.notification_id = notif.id
            self.db.add(sms_notif)
            self.db.commit()
        except IntegrityError as e:
            self.db.rollback()
            raise ValueError("Failed to create notification records") from e
        except Exception:
            self.db.rollback()
            raise

        ok, info = await self.sms_client.send(phone=phone, message=message)
        try:
            notif.status = NotificationStatus.sent if ok else NotificationStatus.failed
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        self.db.refresh(notif)
        self.db.refresh(sms_notif)
        return notif, sms_notif


    # ---------- PUSH ----------
    def _get_push_template_by_purpose(self, purpose: str) -> Template:
        q = (self.db.query(Template)
             .options(joinedload(Template.push_template))
             .filter(Template.type == NotificationType.push,
                     Template.purpose == purpose))
        items: Sequence[Template] = q.all()
        if len(items) == 0:
            raise TemplateNotFoundError(f"No Push Template for type=push, purpose={purpose}")
        if len(items) > 1:
            raise MultipleTemplatesError(f"More than 1 Push Template for type=push, purpose={purpose}")
        tpl = items[0]
        if not tpl.push_template:
            raise TemplateNotFoundError(f"Template '{tpl.name}' has no push_template")
        return tpl

    async def send_push_by_purpose(
            self,
            purpose: str,
            recipient_id: Union[str, UUID],
            *,
            title_params: tuple[str, ...] = (),
            content_params: tuple[str, ...] = (),
    ) -> Tuple[Notification, PushNotification]:

        if not recipient_id:
            raise ValueError("recipient_id is required")

        try:
            recipient_uuid = recipient_id if isinstance(recipient_id, UUID) else UUID(str(recipient_id))
        except (ValueError, TypeError):
            raise ValueError("recipient_id должен быть валидным UUID")

        tpl = self._get_push_template_by_purpose(purpose)
        push_tpl: PushTemplate = tpl.push_template

        title_raw: Optional[str] = push_tpl.title
        content_raw: str = push_tpl.content

        title_txt = self._fmt(title_raw, *title_params) if title_raw else None
        content_txt = self._fmt(content_raw, *content_params)

        notif = Notification(template_id=tpl.id, type=NotificationType.push, status=NotificationStatus.queued)
        push_notif = PushNotification(
            notification_id=None,
            recipient_id=recipient_uuid,
            title=title_txt,
            body=content_txt,
        )

        try:
            self.db.add(notif)
            self.db.flush()
            push_notif.notification_id = notif.id
            self.db.add(push_notif)
            self.db.commit()
        except IntegrityError as e:
            self.db.rollback()
            raise ValueError("Failed to create push notification records") from e
        except Exception:
            self.db.rollback()
            raise

        # 2) отправляем во внешний провайдер
        ok, info = await self.push_client.send(
            recipient_id=str(recipient_uuid),
            content=content_txt,
            title=title_txt,
        )

        # 3) обновляем статус
        try:
            notif.status = NotificationStatus.sent if ok else NotificationStatus.failed
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        self.db.refresh(notif)
        self.db.refresh(push_notif)
        return notif, push_notif
