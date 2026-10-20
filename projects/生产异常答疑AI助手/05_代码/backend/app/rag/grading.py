"""异常分级 Agent：LLM 结构化输出 + 三级兜底（重试→正则提取→默认派单）+ 安全关键词前置。"""
import json
import re
from typing import Optional

from app.core.config import settings
from app.core.logging import get_logger
from app.core.model_factory import get_chat_model
from app.rag.prompts import build_grading_prompt
from app.schemas.grading import GradingResult

logger = get_logger(__name__)

_SAFETY_KEYWORDS = [
    "安全", "事故", "伤亡", "爆炸", "火灾", "中毒", "触电", "高处", "有限空间",
    "防护", "规范", "规程", "作业票", "危化", "泄漏", "灼烫", "机械伤害",
]


def grade_question(question: str, context_hint: str = "") -> GradingResult:
    # 安全关键词前置：不依赖模型自觉
    if any(k in question for k in _SAFETY_KEYWORDS):
        return GradingResult(
            need_ticket=True,
            severity="P0",
            route_type="safety",
            confidence=1.0,
            reason="命中安全/高危关键词，强制派单给安全负责人",
            suggested_checks=["确认作业票证", "停止作业并联系安全员"],
        )

    prompt = build_grading_prompt(question, context_hint)
    llm = get_chat_model()

    # 第一次：直接解析
    text = _invoke(llm, prompt)
    result = _parse_json(text)
    if result:
        return result

    # 第二次：重试
    logger.info("分级第一次解析失败，重试")
    text = _invoke(llm, prompt)
    result = _parse_json(text)
    if result:
        return result

    # 第三次：正则提取首个 {...}
    logger.info("分级第二次解析失败，正则兜底")
    result = _regex_parse(text)
    if result:
        return result

    # 最终兜底：默认派单（宁派单不硬答）
    logger.warning("分级三次解析均失败，兜底为派单")
    return GradingResult(
        need_ticket=True,
        severity="P1",
        route_type="admin",
        confidence=0.0,
        reason="分级模型输出解析失败，按兜底规则派单",
        suggested_checks=[],
    )


def _invoke(llm, prompt: str) -> str:
    try:
        return llm.invoke(prompt).content or ""
    except Exception as e:
        logger.error("分级 LLM 调用失败: %s", e)
        return ""


def _parse_json(text: str) -> Optional[GradingResult]:
    if not text:
        return None
    try:
        data = json.loads(text.strip())
        return GradingResult(**data)
    except Exception:
        return None


def _regex_parse(text: str) -> Optional[GradingResult]:
    if not text:
        return None
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        data = json.loads(m.group())
        return GradingResult(**data)
    except Exception:
        return None
