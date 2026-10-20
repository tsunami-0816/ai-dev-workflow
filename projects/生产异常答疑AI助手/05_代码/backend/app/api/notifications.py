"""通知路由：列表、单条已读、全部已读。"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models import User
from app.schemas.notification import NotificationList, NotificationOut
from app.services import notification_service

router = APIRouter(prefix="/notifications", tags=["通知"])


@router.get("", response_model=NotificationList)
def list_notifications(
    unread_only: bool = Query(False),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items, unread = notification_service.list_notifications(db, user.id, unread_only)
    return NotificationList(
        list=[NotificationOut.model_validate(n) for n in items],
        unread_count=unread,
    )


@router.post("/{notif_id}/read")
def mark_read(notif_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    notification_service.mark_read(db, notif_id, user.id)
    return {"code": 0, "message": "已标记为已读"}


@router.post("/read-all")
def mark_all_read(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    count = notification_service.mark_all_read(db, user.id)
    return {"code": 0, "message": f"已标记 {count} 条为已读"}
