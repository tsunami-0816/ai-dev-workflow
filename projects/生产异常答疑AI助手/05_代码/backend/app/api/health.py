"""健康检查路由。"""
from fastapi import APIRouter

from app.core.config import settings

router = APIRouter(prefix="/health", tags=["健康检查"])


@router.get("")
def health():
    try:
        from app.rag.vectorstore import count_all

        kb_count = count_all()
    except Exception:
        kb_count = -1
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "model_provider": settings.MODEL_PROVIDER,
        "embedding_provider": settings.EMBEDDING_PROVIDER,
        "kb_chunks": kb_count,
    }
