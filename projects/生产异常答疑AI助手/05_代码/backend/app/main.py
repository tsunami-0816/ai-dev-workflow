"""FastAPI 应用入口：注册路由、全局异常、CORS、trace_id 中间件、启动建表。"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    auth,
    chat,
    conversations,
    documents,
    eval as eval_router,
    health,
    knowledge,
    notifications,
    tickets,
    users,
)
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import get_logger, get_trace_id, new_trace_id, setup_logging
from app.db.base import Base
from app.db.engine import engine

setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时确保表存在（首次运行自动建表）
    Base.metadata.create_all(bind=engine)
    logger.info("数据库表已确保存在（如无种子账号请运行 python scripts/init_db.py）")
    yield


app = FastAPI(title=settings.APP_NAME, version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def trace_id_middleware(request: Request, call_next):
    new_trace_id()
    response = await call_next(request)
    response.headers["X-Trace-Id"] = get_trace_id()
    return response


register_exception_handlers(app)

_prefix = settings.API_PREFIX
app.include_router(auth.router, prefix=_prefix)
app.include_router(users.router, prefix=_prefix)
app.include_router(documents.router, prefix=_prefix)
app.include_router(chat.router, prefix=_prefix)
app.include_router(conversations.router, prefix=_prefix)
app.include_router(tickets.router, prefix=_prefix)
app.include_router(notifications.router, prefix=_prefix)
app.include_router(knowledge.router, prefix=_prefix)
app.include_router(eval_router.router, prefix=_prefix)
app.include_router(health.router, prefix=_prefix)


@app.get("/")
def root():
    return {"app": settings.APP_NAME, "version": "0.1.0", "docs": "/docs", "health": f"{_prefix}/health"}
