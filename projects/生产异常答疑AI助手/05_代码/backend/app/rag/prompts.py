"""RAG 生成与异常分级的提示词模板（含中文 few-shot）。"""
from typing import List, Optional

from langchain_core.documents import Document

# ===== RAG 生成系统提示词 =====
RAG_SYSTEM_PROMPT = """你是制造工厂的生产异常答疑助手。严格遵守以下规则：
1. 只能依据【参考资料】中的内容回答，禁止编造手册条款、参数、操作步骤。
2. 回答结构：先给结论，再给「分步操作步骤」（用 1. 2. 3. 编号），最后列出参考来源（文档名+页码/段落）。
3. 如果【参考资料】为空或与问题无关，必须明确回答「未在知识库中找到相关内容，建议转派给对应负责人处理」，禁止猜测。
4. 涉及安全规范、高危操作时，必须追加「请以现场手册为准，必要时停止作业并联系负责人/安全员」。
5. 语言简洁、专业、面向一线员工，不使用晦涩术语。
"""


def build_rag_prompt(question: str, docs: List[Document], history: Optional[List[dict]] = None) -> str:
    context_blocks = []
    for i, d in enumerate(docs, 1):
        m = d.metadata or {}
        src = f"{m.get('doc_name','')} 第{m.get('page','?')}页 {m.get('section','')}"
        context_blocks.append(f"[资料{i}] 来源：{src}\n{d.page_content}")
    context = "\n\n".join(context_blocks) if context_blocks else "（无相关参考资料）"

    history_text = ""
    if history:
        turns = []
        for h in history[-6:]:
            role = "用户" if h.get("role") == "user" else "助手"
            turns.append(f"{role}：{h.get('content','')[:300]}")
        history_text = "\n【对话历史】\n" + "\n".join(turns) + "\n"

    return (
        f"{RAG_SYSTEM_PROMPT}\n\n"
        f"【参考资料】\n{context}\n\n"
        f"{history_text}"
        f"【当前问题】\n{question}\n\n"
        f"请按规则回答："
    )


# ===== 异常分级系统提示词 =====
GRADING_SYSTEM_PROMPT = """你是工厂异常分级助手。判断用户问题是否需要派单，并输出严格 JSON。
规则：
- 简单问题（查手册条款、操作步骤、常识性疑问）→ need_ticket=false
- 复杂问题（设备故障需现场排查、工艺参数异常、安全规范/高危、问题模糊不确定）→ need_ticket=true
- route_type：设备/机械/电气=repair；参数/制程/质量=process；安全=safety；无法判定=admin
- severity：可能导致停机/伤亡=P0；影响生产=P1；一般疑问=P2
- confidence：你对判断的把握 0-1
- 只输出 JSON，不要输出任何解释文字、不要 markdown 代码块。
JSON schema：
{"need_ticket": true/false, "severity": "P0/P1/P2", "route_type": "repair/process/safety/admin", "confidence": 0.0-1.0, "reason": "简要理由", "suggested_checks": ["检查项1"]}
"""

GRADING_FEW_SHOT = """示例1：
问题：CNC 机床报警 E023 主轴过载怎么办？
输出：{"need_ticket": true, "severity": "P1", "route_type": "repair", "confidence": 0.9, "reason": "设备故障需现场排查", "suggested_checks": ["检查主轴负载", "查看刀具是否磨损"]}

示例2：
问题：班前点检表在哪里签字？
输出：{"need_ticket": false, "severity": "P2", "route_type": "admin", "confidence": 0.95, "reason": "常识性流程疑问", "suggested_checks": []}

示例3：
问题：反应釜温度一直降不下来，配方要求 80 度。
输出：{"need_ticket": true, "severity": "P1", "route_type": "process", "confidence": 0.85, "reason": "工艺参数异常需工艺人员介入", "suggested_checks": ["检查冷却水阀", "核对温控仪表"]}

示例4：
问题：进入有限空间作业要办什么票？
输出：{"need_ticket": true, "severity": "P0", "route_type": "safety", "confidence": 0.98, "reason": "高危作业安全规范", "suggested_checks": ["确认作业票证", "气体检测"]}
"""


def build_grading_prompt(question: str, context_hint: str = "") -> str:
    hint = f"\n参考上下文：{context_hint}\n" if context_hint else ""
    return f"{GRADING_SYSTEM_PROMPT}\n{GRADING_FEW_SHOT}\n{hint}\n现在判断这个问题：\n问题：{question}\n输出："
