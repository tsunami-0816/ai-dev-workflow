"""RAG 问答编排：检索 → 受约束生成 → 来源/步骤提取；无相关内容时拒答。"""
import re
import time
from typing import List, Optional, Tuple

from langchain_core.documents import Document

from app.core.logging import get_logger
from app.core.model_factory import get_chat_model
from app.rag.prompts import build_rag_prompt
from app.rag.retriever import hybrid_retrieve
from app.schemas.chat import SourceItem

logger = get_logger(__name__)


def retrieve_and_generate(
    question: str,
    scenario: Optional[str] = None,
    history: Optional[List[dict]] = None,
) -> Tuple[str, List[str], List[SourceItem], bool, int, int]:
    """返回 (answer, steps, sources, no_relevant, retrieve_ms, generate_ms)。"""
    t0 = time.time()
    docs = hybrid_retrieve(question, scenario=scenario)
    retrieve_ms = int((time.time() - t0) * 1000)

    no_relevant = len(docs) == 0
    sources = [_to_source(d) for d in docs]

    t1 = time.time()
    if no_relevant:
        answer = "未在知识库中找到相关内容。为避免误导，建议将此问题转派给对应负责人处理。"
        steps: List[str] = []
    else:
        prompt = build_rag_prompt(question, docs, history or [])
        llm = get_chat_model()
        try:
            answer = llm.invoke(prompt).content or ""
        except Exception as e:
            logger.error("RAG 生成失败: %s", e)
            answer = "答案生成失败，请稍后重试或转派负责人。"
            steps = []
        else:
            steps = _extract_steps(answer)
            # 修复（第8.5步人工渗透反馈）：LLM 判定上下文无关而回答「未找到」时，
            # 检索到的来源与答案矛盾，不应随响应/落库返回，避免误导用户
            if answer.startswith("未在知识库中找到相关内容"):
                sources = []
    generate_ms = int((time.time() - t1) * 1000)
    return answer, steps, sources, no_relevant, retrieve_ms, generate_ms


def _to_source(doc: Document) -> SourceItem:
    m = doc.metadata or {}
    return SourceItem(
        doc_name=str(m.get("doc_name", "")),
        section=str(m.get("section", "")),
        page=m.get("page"),
        text=doc.page_content[:300],
        source_type=str(m.get("source_type", "")),
    )


def _extract_steps(answer: str) -> List[str]:
    """从答案中提取数字编号步骤（1. / 1、 / 1)）。"""
    steps = re.findall(r"(?:^|\n)\s*(?:\d+[.、)])\s*(.+?)(?=(?:\n\s*\d+[.、)])|$)", answer, re.DOTALL)
    cleaned = [s.strip().rstrip("。") for s in steps if s.strip()]
    return cleaned[:8]
