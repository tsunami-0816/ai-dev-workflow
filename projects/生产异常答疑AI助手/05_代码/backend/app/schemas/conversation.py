"""会话与历史消息 schema。"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from .chat import SourceItem


class ConversationOut(BaseModel):
    id: int
    title: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MessageOut(BaseModel):
    id: int
    conversation_id: int
    role: str
    content: str
    sources: Optional[list[SourceItem]] = None
    route_result: Optional[str] = None
    ticket_id: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}
