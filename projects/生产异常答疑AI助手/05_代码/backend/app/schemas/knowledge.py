"""知识沉淀相关 schema。"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ArchiveOut(BaseModel):
    id: int
    standard_question: str
    solution: str
    scenario: str
    tags: str
    source_ticket_id: Optional[str] = None
    source_doc: str
    status: str  # pending / approved / rejected
    indexed: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ReviewRequest(BaseModel):
    approve: bool
    reject_reason: str = ""
