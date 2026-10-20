"""通用响应与分页模型。"""
from typing import Generic, List, Optional, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    code: int = 0
    message: str = "ok"
    data: Optional[T] = None
    trace_id: str = ""


class PageResult(BaseModel, Generic[T]):
    # 字段名 list 会遮蔽内置 list，注解必须用 typing.List（大写 L）
    list: List[T] = []
    total: int = 0
    page: int = 1
    page_size: int = 20
