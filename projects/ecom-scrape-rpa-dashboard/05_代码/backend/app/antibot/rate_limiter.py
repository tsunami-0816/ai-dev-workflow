"""单域名令牌桶限速（L2 / T03 / D-09、D-83）。

为什么自研不用第三方：桶的行为（容量 1、按 qps 补充、await 而非 sleep 后硬闯）
是 C03 的被测对象，被框架包住就无法取证（ADR-01 同理）。
进程内单例（D-83）：同进程所有采集任务共用同一组桶，防止两个任务并发把限速打穿。
时间用 time.monotonic()：墙钟回拨不会导致连发（R-06）。

关键设计：gate() 必须在「发送前一刻」调用（所有 header/客户端准备完成之后）。
桶按实际发送时刻推进——若按取号时刻推进，首次请求的客户端构建耗时
（SSL context 约 0.7s）会挤占下一个槽位，实测相邻请求间隔会小于 1/qps（C03 破防）。
"""
from __future__ import annotations

import asyncio
import time

# domain -> 桶（进程内唯一入口 gate，D-83）
_BUCKETS: dict[str, "_Bucket"] = {}
_LOCK = asyncio.Lock()


class _Bucket:
    """容量 1 的漏桶变体：next_available 单调前进，间隔 = 1/qps 秒。"""

    __slots__ = ("interval", "next_available")

    def __init__(self, qps: float):
        self.interval = 1.0 / qps
        self.next_available = time.monotonic()

    def reserve(self) -> float:
        """占一个发送槽位：返回允许发送的 monotonic 时刻。

        以 max(next_available, now) 为槽位起点（排队时保持稳定节奏，
        C03 按 MIN(diff) 判定而非平均值）。
        """
        now = time.monotonic()
        slot = max(self.next_available, now)
        self.next_available = slot + self.interval
        return slot


async def gate(domain: str, qps: float) -> int:
    """发送前一刻调用：等到允许发送再返回。返回实际等待毫秒（写 wait_ms，C03 证据）。

    拿不到令牌就 await，不是 sleep 后硬闯（架构 §3 L2 第 1 步）。
    sleep 放在锁外：先占槽（锁内瞬时完成），再睡到自己的槽位。
    """
    async with _LOCK:
        bucket = _BUCKETS.get(domain)
        if bucket is None:
            bucket = _Bucket(qps)
            _BUCKETS[domain] = bucket
        elif bucket.interval < 1.0 / qps:
            # 竞态下 qps 取较小者：配置收紧时旧桶不会继续放行旧速率
            bucket.interval = 1.0 / qps
        slot = bucket.reserve()
    delay = slot - time.monotonic()
    if delay > 0:
        await asyncio.sleep(delay)
        return int(delay * 1000)
    return 0


# 兼容旧调用名（tests / 文档口径）
async def acquire(domain: str, qps: float) -> int:
    return await gate(domain, qps)


def reset_for_tests() -> None:
    _BUCKETS.clear()
