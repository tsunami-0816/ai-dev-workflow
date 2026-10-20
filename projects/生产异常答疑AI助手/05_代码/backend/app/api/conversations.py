"""多轮会话路由：会话列表、历史消息。"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models import User
from app.schemas.conversation import ConversationOut, MessageOut
from app.services import conversation_service

router = APIRouter(prefix="/conversations", tags=["会话"])


@router.get("", response_model=list[ConversationOut])
def list_conversations(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return [ConversationOut.model_validate(c) for c in conversation_service.list_conversations(db, user.id)]


@router.get("/{conv_id}/messages", response_model=list[MessageOut])
def list_messages(conv_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return [
        MessageOut.model_validate(m)
        for m in conversation_service.list_messages(db, conv_id, user.id)
    ]
