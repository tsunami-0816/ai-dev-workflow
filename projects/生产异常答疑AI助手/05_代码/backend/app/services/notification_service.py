"""系统内通知服务：按角色批量生成、列表、已读。"""
from sqlalchemy.orm import Session

from app.core.exceptions import AppError, ERR_NOT_FOUND
from app.models import Notification, User


def create_notifications_for_role(
    db: Session, role: str, title: str, content: str, ref_id: str, ref_type: str = "ticket"
) -> int:
    users = db.query(User).filter(User.role == role, User.is_active == True).all()  # noqa: E712
    count = 0
    for u in users:
        db.add(
            Notification(
                user_id=u.id,
                type="ticket_assign",
                title=title,
                content=content,
                ref_type=ref_type,
                ref_id=ref_id,
            )
        )
        count += 1
    db.commit()
    return count


def list_notifications(db: Session, user_id: int, unread_only: bool = False) -> tuple[list[Notification], int]:
    q = db.query(Notification).filter(Notification.user_id == user_id)
    if unread_only:
        q = q.filter(Notification.is_read == False)  # noqa: E712
    items = q.order_by(Notification.created_at.desc()).limit(100).all()
    unread = (
        db.query(Notification)
        .filter(Notification.user_id == user_id, Notification.is_read == False)  # noqa: E712
        .count()
    )
    return items, unread


def mark_read(db: Session, notif_id: int, user_id: int) -> None:
    n = db.query(Notification).filter(Notification.id == notif_id, Notification.user_id == user_id).first()
    if not n:
        raise AppError(ERR_NOT_FOUND, "通知不存在", http_status=404)
    n.is_read = True
    db.commit()


def mark_all_read(db: Session, user_id: int) -> int:
    count = (
        db.query(Notification)
        .filter(Notification.user_id == user_id, Notification.is_read == False)  # noqa: E712
        .update({Notification.is_read: True})
    )
    db.commit()
    return count
