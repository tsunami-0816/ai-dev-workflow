"""模型工厂：按 MODEL_PROVIDER / EMBEDDING_PROVIDER 切换本地 Ollama 与云端 API。
本地与云端均走 OpenAI 兼容接口，业务代码不绑定具体厂商。"""
from functools import lru_cache
from typing import List

from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from .config import settings
from .logging import get_logger

logger = get_logger(__name__)

try:
    from langchain_community.embeddings import HuggingFaceEmbeddings  # type: ignore
except Exception:  # pragma: no cover
    HuggingFaceEmbeddings = None  # type: ignore


class _LocalBGEEmbeddings(Embeddings):
    """直接封装 sentence-transformers，避免 langchain 版本兼容问题。"""

    def __init__(self, model_name: str):
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(model_name, device="cpu")

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return self._model.encode(texts, normalize_embeddings=True, show_progress_bar=False).tolist()

    def embed_query(self, text: str) -> List[float]:
        return self._model.encode([text], normalize_embeddings=True, show_progress_bar=False).tolist()[0]


@lru_cache(maxsize=2)
def get_chat_model() -> BaseChatModel:
    """返回聊天模型。本地 Ollama 或云端 API，均为 OpenAI 兼容。"""
    if settings.MODEL_PROVIDER == "api":
        if not settings.API_BASE_URL or not settings.API_KEY:
            logger.warning("MODEL_PROVIDER=api 但 API_BASE_URL/API_KEY 未配置，回退本地")
            return _local_chat()
        logger.info("使用云端模型: %s @ %s", settings.API_MODEL, settings.API_BASE_URL)
        return ChatOpenAI(
            model=settings.API_MODEL,
            api_key=settings.API_KEY,
            base_url=settings.API_BASE_URL,
            temperature=0.1,
            timeout=60,
            max_retries=1,
        )
    return _local_chat()


def _local_chat() -> BaseChatModel:
    logger.info("使用本地 Ollama 模型: %s @ %s", settings.LOCAL_MODEL, settings.LOCAL_BASE_URL)
    # Ollama 暴露 OpenAI 兼容端点，api_key 可为任意非空字符串
    return ChatOpenAI(
        model=settings.LOCAL_MODEL,
        api_key="ollama",
        base_url=settings.LOCAL_BASE_URL,
        temperature=0.1,
        timeout=120,
        max_retries=1,
    )


@lru_cache(maxsize=2)
def get_embeddings() -> Embeddings:
    """返回 Embedding 模型。本地 HuggingFace(bge) 或云端 API。"""
    if settings.EMBEDDING_PROVIDER == "api":
        if not settings.API_BASE_URL or not settings.API_KEY:
            logger.warning("EMBEDDING_PROVIDER=api 但未配置，回退本地 bge")
            return _local_embeddings()
        logger.info("使用云端 Embedding: %s", settings.API_EMBEDDING_MODEL)
        return OpenAIEmbeddings(
            model=settings.API_EMBEDDING_MODEL,
            api_key=settings.API_KEY,
            base_url=settings.API_BASE_URL,
            timeout=60,
        )
    return _local_embeddings()


def _local_embeddings() -> Embeddings:
    logger.info("使用本地 Embedding: %s (CPU)", settings.EMBEDDING_MODEL)
    if HuggingFaceEmbeddings is not None:
        try:
            return HuggingFaceEmbeddings(
                model_name=settings.EMBEDDING_MODEL,
                model_kwargs={"device": "cpu"},
                encode_kwargs={"normalize_embeddings": True},
            )
        except Exception as e:
            logger.warning("HuggingFaceEmbeddings 初始化失败(%s)，回退直接封装", e)
    return _LocalBGEEmbeddings(settings.EMBEDDING_MODEL)
