"""混合检索：向量(top-k) + BM25(中文 jieba) → EnsembleRetriever 合并去重。"""
from typing import List, Optional

from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document
from langchain.retrievers import EnsembleRetriever

from app.core.config import settings
from app.core.logging import get_logger
from app.rag.vectorstore import get_vectorstore

logger = get_logger(__name__)


def _load_all_docs() -> List[Document]:
    """从 Chroma 加载全部切片，供 BM25 建内存索引。"""
    vs = get_vectorstore()
    res = vs._collection.get(include=["documents", "metadatas"])
    docs: List[Document] = []
    for text, meta in zip(res.get("documents", []), res.get("metadatas", [])):
        if text:
            docs.append(Document(page_content=text, metadata=meta or {}))
    return docs


def hybrid_retrieve(
    query: str,
    scenario: Optional[str] = None,
    top_k: Optional[int] = None,
) -> List[Document]:
    """混合检索，返回去重后的 top_k 条相关文档。空库返回 []。"""
    top_k = top_k or settings.ENSEMBLE_TOP_K
    vs = get_vectorstore()

    # 向量检索（可按 scenario 元数据过滤）；同时取距离，供 ACC-01 相关性守门使用
    search_kwargs: dict = {"k": settings.RETRIEVE_TOP_K}
    if scenario:
        search_kwargs["filter"] = {"scenario": scenario}
    vec_retriever = vs.as_retriever(search_kwargs=search_kwargs)
    if scenario:
        vec_hits = vs.similarity_search_with_score(
            query, k=settings.RETRIEVE_TOP_K, filter={"scenario": scenario}
        )
    else:
        vec_hits = vs.similarity_search_with_score(query, k=settings.RETRIEVE_TOP_K)

    # BM25 检索（中文分词，重命中设备型号/故障代码）
    all_docs = _load_all_docs()
    if not all_docs:
        logger.info("知识库为空，检索返回空")
        return []
    try:
        # 建索引时即传入中文分词器，保证查询与索引分词一致
        bm25_retriever = BM25Retriever.from_documents(
            all_docs, k=settings.RETRIEVE_TOP_K, preprocess_func=_jieba_cut
        )
    except Exception as e:
        logger.warning("BM25 初始化失败，回退纯向量检索: %s", e)
        return _vector_gate_filter(vec_hits, top_k)

    ensemble = EnsembleRetriever(retrievers=[vec_retriever, bm25_retriever], weights=[0.6, 0.4])
    try:
        results = ensemble.invoke(query)
    except Exception as e:
        logger.error("混合检索失败，回退纯向量: %s", e)
        return _vector_gate_filter(vec_hits, top_k)

    # === ACC-01 相关性守门（第 9 步验收修复） ===
    # 实测依据（2026-10-20，bge-small-zh + Chroma L2）：库内问题 top 距离 ≤0.762，
    # 库外问题 ≥0.915，取 0.85 为门槛；向量过门槛 OR BM25 分词强命中（score>0）才保留。
    allowed: set = set()
    for d, dist in vec_hits:
        if float(dist) <= settings.MAX_VECTOR_DISTANCE:
            allowed.add(d.page_content[:120].strip())
    try:
        bm_scores = bm25_retriever.bm25.get_scores(_jieba_cut(query))
        top_idx = sorted(range(len(bm_scores)), key=lambda i: bm_scores[i], reverse=True)
        for i in top_idx[: settings.RETRIEVE_TOP_K]:
            if bm_scores[i] > 0:
                allowed.add(all_docs[i].page_content[:120].strip())
    except Exception as e:
        logger.warning("BM25 得分计算失败，仅用向量门槛: %s", e)

    # 按内容去重（仅保留通过相关性守门的切片）
    seen = set()
    unique: List[Document] = []
    for d in results:
        key = d.page_content[:120].strip()
        if not key or key in seen or key not in allowed:
            continue
        seen.add(key)
        unique.append(d)
        if len(unique) >= top_k:
            break
    if not unique:
        logger.info("相关性守门拒绝全部检索结果，query=%s", query[:50])
    return unique


def _vector_gate_filter(vec_hits, top_k: int) -> List[Document]:
    """ACC-01 回退路径守门：仅保留向量距离过门槛的切片。"""
    kept = [d for d, dist in vec_hits if float(dist) <= settings.MAX_VECTOR_DISTANCE]
    return kept[:top_k]


def _jieba_cut(text: str) -> List[str]:
    try:
        import jieba

        return [w for w in jieba.cut(text) if w.strip()]
    except ImportError:
        return list(text)
