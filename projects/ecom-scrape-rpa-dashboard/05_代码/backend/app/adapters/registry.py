"""适配器注册表（T05 / D-15）。

platform → adapter 的唯一映射；并发信号量也在这里按 sites.yaml 配置发放
（架构 §1.4：京东 4 / 天猫 2 / 拼多多 2 / 抖音 1 / mock 4）。
"""
from __future__ import annotations

import asyncio

from app.adapters.base import BaseAdapter, FetchContext
from app.adapters.douyin import DouyinAdapter
from app.adapters.jd import JdAdapter
from app.adapters.mock import MockAdapter
from app.adapters.pdd import PddAdapter
from app.adapters.tmall import TmallAdapter
from app.config import ConfigError

_REGISTRY: dict[str, type[BaseAdapter]] = {
    "jd": JdAdapter,
    "tmall": TmallAdapter,
    "pdd": PddAdapter,
    "douyin": DouyinAdapter,
    "mock": MockAdapter,
}

_SEMAPHORES: dict[str, asyncio.Semaphore] = {}


def get_adapter(platform: str, ctx: FetchContext) -> BaseAdapter:
    if platform not in _REGISTRY:
        raise ConfigError(f"未知平台 {platform!r}，可选: {sorted(_REGISTRY)}")
    # MOCK_MODE=1 时 BaseAdapter.base_url() 自动指向 mock_site（Mock 红线：默认不出网）
    return _REGISTRY[platform](ctx)


def concurrency_slot(platform: str) -> asyncio.Semaphore:
    """域内并发信号量（进程内单例）：封禁降级时改 sites.yaml 即收紧（D-02）。"""
    from app.config import site_cfg

    if platform not in _SEMAPHORES:
        _SEMAPHORES[platform] = asyncio.Semaphore(int(site_cfg(platform)["concurrency"]))
    return _SEMAPHORES[platform]
