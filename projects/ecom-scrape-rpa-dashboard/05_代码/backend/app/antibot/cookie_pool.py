"""Cookie 池（L2 / T03 / D-11）。

Cookie 是用户凭据：只从 config/cookies/<platform>.json（.gitignore）装载，永不出现在代码。
空池 → 走无 Cookie 路径并在 antibot_metrics.cookie_state='none'（架构 §3 L2 第 3 步），
这是 R-02「无真实账号」的兜底路径，不是错误。
"""
from __future__ import annotations

import json
from pathlib import Path

from app.config import BACKEND_ROOT

_STATE: dict[str, str] = {}  # platform -> 'none' / 'ok' / 'invalid'（进程内探测结果）


def _cookie_path(platform: str) -> Path:
    return BACKEND_ROOT / "config" / "cookies" / f"{platform}.json"


def acquire(platform: str) -> tuple[str | None, str]:
    """取 Cookie 头：返回 (cookie_header or None, state)。

    state ∈ none/ok/invalid：none=空池直连；invalid=上次探测失效已跳过。
    """
    path = _cookie_path(platform)
    if _STATE.get(platform) == "invalid" or not path.exists():
        _STATE.setdefault(platform, "none")
        return None, _STATE[platform]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        header = data.get("cookie", "") if isinstance(data, dict) else ""
    except (json.JSONDecodeError, OSError):
        # 文件坏了按空池降级（边界输入：文件/路径均可降级不 crash，§8）
        _STATE[platform] = "none"
        return None, "none"
    if not header.strip():
        _STATE[platform] = "none"
        return None, "none"
    _STATE[platform] = "ok"
    return header, "ok"


def mark_invalid(platform: str) -> None:
    """302→登录页或失效探测命中后调用：标记 invalid 并从本轮轮换剔除。"""
    _STATE[platform] = "invalid"


def reset_for_tests() -> None:
    _STATE.clear()
