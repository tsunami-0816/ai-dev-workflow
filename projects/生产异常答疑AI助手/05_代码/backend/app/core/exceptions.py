"""统一异常与错误码：所有业务异常转换为 {code,message,data,trace_id}。"""
from typing import Any, Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from .logging import get_logger, get_trace_id

logger = get_logger(__name__)


class AppError(Exception):
    """业务异常基类。code 区间见错误码表。"""

    def __init__(self, code: int, message: str, data: Any = None, http_status: int = 400):
        self.code = code
        self.message = message
        self.data = data
        self.http_status = http_status
        super().__init__(message)


# ===== 错误码表 =====
# 1000 参数/校验；2000 检索/知识库；3000 模型/Agent；4000 工单/业务；5000 系统
ERR_PARAM = 1001
ERR_UNSUPPORTED_TYPE = 1002
ERR_FILE_TOO_LARGE = 1003
ERR_UNAUTHORIZED = 1004
ERR_FORBIDDEN = 1005
ERR_NOT_FOUND = 1006

ERR_KB_EMPTY = 2001
ERR_NO_RELEVANT = 2002  # 无足够相关内容，引导拒答/派单

ERR_MODEL_UNAVAILABLE = 3001
ERR_GRADING_PARSE = 3002  # 分级结构化输出解析失败
ERR_MODEL_TIMEOUT = 3003

ERR_TICKET_NOT_FOUND = 4001
ERR_INVALID_TRANSITION = 4002  # 工单状态机非法流转

ERR_INTERNAL = 5001
ERR_DOWNSTREAM = 5003


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError):
        logger.warning("AppError code=%s msg=%s", exc.code, exc.message)
        return JSONResponse(
            status_code=exc.http_status,
            content={
                "code": exc.code,
                "message": exc.message,
                "data": exc.data,
                "trace_id": get_trace_id(),
            },
        )

    @app.exception_handler(ValidationError)
    async def handle_validation_error(request: Request, exc: ValidationError):
        logger.warning("ValidationError: %s", exc)
        return JSONResponse(
            status_code=422,
            content={
                "code": ERR_PARAM,
                "message": "请求参数校验失败",
                "data": exc.errors(),
                "trace_id": get_trace_id(),
            },
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception):
        logger.exception("Unhandled exception: %s", exc)
        return JSONResponse(
            status_code=500,
            content={
                "code": ERR_INTERNAL,
                "message": "服务器内部错误，请联系管理员",
                "data": None,
                "trace_id": get_trace_id(),
            },
        )
