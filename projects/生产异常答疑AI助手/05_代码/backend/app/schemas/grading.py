"""异常分级 Agent 的结构化输出 schema（LLM 必须输出此 JSON）。"""
from pydantic import BaseModel, Field


class GradingResult(BaseModel):
    """分级结果。need_ticket=true 时必须给出 route_type 与 reason。"""

    need_ticket: bool = Field(..., description="是否需要派单：简单问题 false，复杂/高风险/不确定 true")
    severity: str = Field(default="P1", pattern="^(P0|P1|P2)$", description="紧急等级")
    route_type: str = Field(
        default="admin",
        pattern="^(repair|process|safety|admin)$",
        description="负责人类型：设备/机械/电气=repair；参数/制程/质量=process；安全=safety；无法判定=admin",
    )
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="分级置信度 0-1")
    reason: str = Field(default="", description="分级与路由的简要理由")
    suggested_checks: list[str] = Field(default_factory=list, description="建议负责人先做的检查项")
