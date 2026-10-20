"""通知相关 schema。"""
from datetime import datetime

from pydantic import BaseModel, Field


class NotificationOut(BaseModel):
    id: int
    type: str
    title: str
    content: str
    ref_type: str
    ref_id: str
    is_read: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class NotificationList(BaseModel):
    # 修复-第6步冒烟：字段名 list 遮蔽内置 list 类型，导致 Pydantic 重建注解时
    # 把已绑定的字段值（list 实例）当下标用，抛 TypeError。改名 items + alias 保持对外字段名不变。
    items: list[NotificationOut] = Field(default=[], alias="list")
    unread_count: int = 0

    model_config = {"populate_by_name": True}
