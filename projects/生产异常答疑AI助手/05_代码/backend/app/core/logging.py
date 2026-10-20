"""结构化日志配置：统一格式、可按 trace_id 串联一次请求。"""
import logging
import uuid
from contextvars import ContextVar

# 请求级 trace_id，中间件写入，业务代码读取
_trace_id: ContextVar[str] = ContextVar("trace_id", default="")


def new_trace_id() -> str:
    tid = f"tr-{uuid.uuid4().hex[:12]}"
    _trace_id.set(tid)
    return tid


def get_trace_id() -> str:
    return _trace_id.get() or "no-trace"


class TraceFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = get_trace_id()
        return True


def setup_logging(level: int = logging.INFO) -> None:
    root = logging.getLogger()
    if root.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)-7s | %(trace_id)s | %(name)s | %(message)s"
        )
    )
    handler.addFilter(TraceFilter())
    root.addHandler(handler)
    root.setLevel(level)
    # 降低第三方库噪音
    for noisy in ("httpx", "urllib3", "chromadb", "sentence_transformers"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
