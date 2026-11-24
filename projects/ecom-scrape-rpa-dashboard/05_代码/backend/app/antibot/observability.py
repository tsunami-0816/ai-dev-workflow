"""观测与风控识别（L2 / T04 / D-14、D-21）。

风控页启发式识别：HTTP 200 但内容是验证码/受限页时，把"假 200"判成失败，
否则 C02 成功率会虚高（架构 §7.1）。识别信号：
1. 关键词：验证码 / 访问受限 / 请稍后再试；
2. 302 → 登录页（follow_redirects=False 才能拿到 302 本身）。
每次请求写一行 antibot_metrics（只追加，P1-03：at=发起时刻，finished_at 单独记录）。
"""
from __future__ import annotations

from datetime import datetime

from app import db
from app.config import now_cn

BLOCK_KEYWORDS = ("验证码", "访问受限", "请稍后再试", "请完成下方验证")

_METRIC_SQL = (
    "INSERT INTO antibot_metrics "
    "(platform, url, http_status, latency_ms, wait_ms, via_proxy, cookie_state, "
    " blocked_flag, block_reason, retry_no, run_id, at, finished_at) "
    "VALUES (%(platform)s, %(url)s, %(http_status)s, %(latency_ms)s, %(wait_ms)s, "
    "%(via_proxy)s, %(cookie_state)s, %(blocked_flag)s, %(block_reason)s, "
    "%(retry_no)s, %(run_id)s, %(at)s, %(finished_at)s)"
)


def detect_block(status: int | None, headers: dict, text: str) -> tuple[bool, str | None]:
    """返回 (blocked_flag, block_reason)。reason ∈ captcha/login_redirect/rate_limit/keyword。"""
    if status is not None and 300 <= status < 400:
        location = str(headers.get("location", "")).lower()
        if "login" in location or "passport" in location:
            return True, "login_redirect"
        return False, None
    if status == 429:
        return True, "rate_limit"
    if status is not None and 200 <= status < 300 and text:
        hit = next((kw for kw in BLOCK_KEYWORDS if kw in text[:5000]), None)
        if hit:
            return True, "captcha" if hit == "验证码" else "keyword"
    return False, None


def record_metric(
    *,
    platform: str,
    url: str,
    http_status: int | None,
    latency_ms: int,
    wait_ms: int = 0,
    via_proxy: bool = False,
    cookie_state: str = "none",
    blocked_flag: bool = False,
    block_reason: str | None = None,
    retry_no: int = 0,
    run_id: int | None = None,
    at: datetime,
    finished_at: datetime | None = None,
) -> None:
    """落一行观测数据（同步写：观测不能因 DB 抖动丢行，失败由调用方记日志）。"""
    db.execute(
        _METRIC_SQL,
        dict(
            platform=platform[:16],
            url=url[:512],
            http_status=http_status,
            latency_ms=int(latency_ms),
            wait_ms=int(wait_ms),
            via_proxy=1 if via_proxy else 0,
            cookie_state=cookie_state[:16],
            blocked_flag=1 if blocked_flag else 0,
            block_reason=block_reason,
            retry_no=retry_no,
            run_id=run_id,
            at=at,
            finished_at=finished_at or now_cn(),
        ),
    )
