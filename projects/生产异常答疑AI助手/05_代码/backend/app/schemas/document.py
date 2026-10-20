"""知识库文档相关 schema。"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class DocumentOut(BaseModel):
    id: int
    filename: str
    doc_type: str
    scenario: str
    chunk_count: int
    status: str
    uploaded_by: str
    error_msg: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UploadResponse(BaseModel):
    document_id: int
    filename: str
    status: str
    message: str = "文档已提交入库"
