"""工单相关 schema。"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class TicketOut(BaseModel):
    id: str
    title: str
    question: str
    route_type: str
    severity: str
    status: str
    confidence: float
    llm_reason: Optional[str] = None
    answer_snapshot: Optional[str] = None
    created_by_user_id: int
    assignee_role: str
    assignee: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    closed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class TicketCreate(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    route_type: str = Field(..., pattern="^(repair|process|safety|admin)$")
    severity: str = Field(default="P1", pattern="^(P0|P1|P2)$")
    title: str = ""
    reason: str = ""


class HandleRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=4000)


class CloseRequest(BaseModel):
    archive: bool = False  # 关闭时是否沉淀为知识
    solution: str = ""  # 最终解决步骤（若未在 handle 中填写）


class TicketHandlingOut(BaseModel):
    id: int
    ticket_id: str
    handler: str
    action: str
    content: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}
