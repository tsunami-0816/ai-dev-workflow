"""多轮问答相关 schema。"""
from typing import Optional

from pydantic import BaseModel, Field

from .grading import GradingResult


class SourceItem(BaseModel):
    doc_name: str = ""
    section: str = ""
    page: Optional[int] = None
    text: str = ""
    source_type: str = ""  # 手册 / 归档知识


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    conversation_id: Optional[int] = None
    scenario: Optional[str] = None  # 可选过滤：设备故障/工艺异常/安全规范


class AskResponse(BaseModel):
    conversation_id: int
    message_id: int
    answer: str
    steps: list[str] = Field(default_factory=list)
    sources: list[SourceItem] = Field(default_factory=list)
    route_result: str  # answer / ticket
    need_ticket: bool
    ticket_id: Optional[str] = None
    grading: Optional[GradingResult] = None
    no_relevant: bool = False  # 无相关内容时为 true，引导拒答/派单
    retrieve_ms: int = 0
    generate_ms: int = 0
    total_ms: int = 0
    trace_id: str = ""


class FeedbackRequest(BaseModel):
    trace_id: str
    vote: str = Field(..., pattern="^(up|down)$")
    comment: str = ""
