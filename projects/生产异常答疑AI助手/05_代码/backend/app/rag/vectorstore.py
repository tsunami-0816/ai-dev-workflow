"""Chroma 持久化向量库：获取、入库、按 doc_id 删除。"""
import os
from typing import List

from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document

from app.core.config import settings
from app.core.logging import get_logger
from app.core.model_factory import get_embeddings

logger = get_logger(__name__)

_COLLECTION_NAME = "factory_kb"


def get_vectorstore() -> Chroma:
    os.makedirs(settings.CHROMA_DIR, exist_ok=True)
    return Chroma(
        collection_name=_COLLECTION_NAME,
        embedding_function=get_embeddings(),
        persist_directory=settings.CHROMA_DIR,
    )


def add_documents(docs: List[Document]) -> int:
    if not docs:
        return 0
    # 修复-第6步冒烟：兜底清理 None metadata。即使上游 _meta 已过滤，
    # splitter 或 LangChain 内部也可能把某些 metadata 键置 None，
    # Chroma upsert 遇到任何 None 值都会直接抛异常。
    from langchain_community.vectorstores.utils import filter_complex_metadata
    clean = []
    for d in docs:
        if not d.page_content or not d.page_content.strip():
            continue  # 跳过空切片
        try:
            filtered_meta = filter_complex_metadata(d.metadata)
        except Exception:
            filtered_meta = {k: v for k, v in d.metadata.items()
                             if isinstance(v, (str, int, float, bool))}
        d.metadata = filtered_meta
        clean.append(d)
    if not clean:
        logger.warning("切片过滤后无有效内容（原 %d 条）", len(docs))
        return 0
    vs = get_vectorstore()
    vs.add_documents(clean)
    logger.info("向量化入库 %d 条切片", len(clean))
    return len(clean)


def delete_by_doc_id(doc_id: int) -> None:
    """按 metadata.doc_id 删除该文档的全部向量。"""
    vs = get_vectorstore()
    try:
        vs._collection.delete(where={"doc_id": doc_id})
        logger.info("已删除 doc_id=%s 的向量", doc_id)
    except Exception as e:
        logger.error("删除向量失败 doc_id=%s: %s", doc_id, e)
        raise


def count_all() -> int:
    vs = get_vectorstore()
    return vs._collection.count()
