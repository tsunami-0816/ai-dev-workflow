"""多轮会话与历史消息服务。"""
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.core.exceptions import AppError, ERR_FORBIDDEN, ERR_NOT_FOUND
from app.models import Conversation, Message


def create_conversation(db: Session, user_id: int, title: str = "新会话") -> Conversation:
    conv = Conversation(title=title or "新会话", user_id=user_id)
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


def list_conversations(db: Session, user_id: int) -> list[Conversation]:
    return (
        db.query(Conversation)
        .filter(Conversation.user_id == user_id)
        .order_by(Conversation.updated_at.desc())
        .all()
    )


def get_conversation(db: Session, conv_id: int, user_id: int) -> Conversation:
    conv = db.query(Conversation).filter(Conversation.id == conv_id).first()
    if not conv:
        raise AppError(ERR_NOT_FOUND, "会话不存在", http_status=404)
    if conv.user_id != user_id:
        raise AppError(ERR_FORBIDDEN, "无权访问该会话", http_status=403)
    return conv


def list_messages(db: Session, conv_id: int, user_id: int) -> list[Message]:
    get_conversation(db, conv_id, user_id)
    return (
        db.query(Message)
        .filter(Message.conversation_id == conv_id)
        .order_by(Message.id.asc())
        .all()
    )


def add_message(
    db: Session,
    conv_id: int,
    role: str,
    content: str,
    sources: Optional[list] = None,
    route_result: Optional[str] = None,
    ticket_id: Optional[str] = None,
) -> Message:
    msg = Message(
        conversation_id=conv_id,
        role=role,
        content=content,
        sources=sources,
        route_result=route_result,
        ticket_id=ticket_id,
    )
    db.add(msg)
    conv = db.query(Conversation).filter(Conversation.id == conv_id).first()
    if conv:
        if role == "user" and (conv.title == "新会话" or not conv.title):
            conv.title = content[:20]
        conv.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(msg)
    return msg
