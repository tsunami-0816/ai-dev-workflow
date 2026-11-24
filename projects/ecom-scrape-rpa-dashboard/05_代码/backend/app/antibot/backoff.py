"""指数退避与长冷却（L2 / T03 / D-13）。

两类失败走两条路（顺序固定写进 ops.md）：
- 429/503 → 长冷却 30s 起再重试，不走普通退避（被限流时退避 1s 等于硬闯）；
- 网络错误 → 指数退避 1s×2^n，最多 3 次（架构 §3 L2 失败与降级）。
"""
from __future__ import annotations

MAX_RETRIES = 3


def delay_for_network_error(retry_no: int) -> float:
    """网络错误退避：1s × 2^retry_no（retry_no 从 0 起）。"""
    return min(1.0 * (2 ** max(0, retry_no)), 8.0)


def cooldown_for_status(status: int) -> float | None:
    """429/503 的长冷却；其他状态返回 None（走网络退避或不重试）。"""
    if status in (429, 503):
        return 30.0
    return None


def is_retryable_status(status: int | None) -> bool:
    return status in (429, 503, 502)
