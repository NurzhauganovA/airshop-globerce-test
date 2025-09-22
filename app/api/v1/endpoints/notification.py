# app/api/v1/endpoints/sms_notification.py

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.controllers.notification_controller import (
    TemplateController,
    NotificationController,
)
from app.schemas.notification_schemas import (
    TemplateList,
    SmsSendByRequest,
    SmsSendResponse,
    TemplateCreate,
    TemplateOut,
    NotificationStatus,
    NotificationType, PushSendResponse, PushSendByRequest
)

router = APIRouter()


@router.post("/templates", response_model=TemplateOut)
def create_template(payload: TemplateCreate, db: Session = Depends(get_db)):
    ctrl = TemplateController(db)
    tpl = ctrl.create(payload)
    return TemplateOut(
        id=str(tpl.id), name=tpl.name, purpose=tpl.purpose, type=tpl.type
    )


@router.get("/templates", response_model=TemplateList)
def list_templates(
    offset: int = 0, limit: int = Query(50, le=200), db: Session = Depends(get_db)
):
    ctrl = TemplateController(db)
    items, total = ctrl.list(offset, limit)
    mapped = []
    for t in items:
        mapped.append(
            TemplateOut(
                id=str(t.id),
                name=t.name,
                purpose=t.purpose,  # <-- добавили
                type=(
                    t.type
                    if isinstance(t.type, NotificationType)
                    else NotificationType(t.type)
                ),  #
            )
        )
    return TemplateList(items=mapped, total=total)


@router.post("/send", response_model=SmsSendResponse)
async def send_sms(req: SmsSendByRequest, db: Session = Depends(get_db)):
    ctrl = NotificationController(db)
    try:
        n, s = await ctrl.send_sms_by_purpose(
            "STORE_EMPLOYEE_WELCOME", req.phone, "7777"
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return SmsSendResponse(id=str(n.id), status=NotificationStatus(n.status.value), phone=s.phone)

@router.post("/push/send", response_model=PushSendResponse)
async def send_push(req: PushSendByRequest, db: Session = Depends(get_db)):
    ctrl = NotificationController(db)
    try:
        notif, push = await ctrl.send_push_by_purpose(
            purpose="TAK_TAK",
            recipient_id=req.recipient_id,
            title_params=tuple(req.title_params),
            content_params=tuple(req.content_params),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return PushSendResponse(
        id=str(notif.id),
        status=NotificationStatus(notif.status.value),
        recipient_id=str(push.recipient_id),
    )