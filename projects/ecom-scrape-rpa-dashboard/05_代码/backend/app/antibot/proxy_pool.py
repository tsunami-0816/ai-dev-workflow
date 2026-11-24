"""代理池（L2 / T03 / D-12）。

proxies.txt 一行一个 http://user:pass@host:port；空文件 = 直连（via_proxy=0）。
连续失败 2 次标记 unhealthy 并切下一个（架构 §3 L2 第 4 步）。
凭据只在 proxies.txt（.gitignore），不进代码。
"""
from __future__ import annotations

from pathlib import Path

from app.config import BACKEND_ROOT


class ProxyPool:
    def __init__(self, path: Path | None = None):
        self._path = path or (BACKEND_ROOT / "config" / "proxies.txt")
        self._proxies: list[str] = []
        self._fail: dict[str, int] = {}
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            lines = [
                ln.strip()
                for ln in self._path.read_text(encoding="utf-8").splitlines()
                if ln.strip() and not ln.startswith("#")
            ]
            self._proxies = lines

    def pick(self) -> str | None:
        """取第一个健康代理；全空/全不健康 → None（直连，降级而非报错）。"""
        for p in self._proxies:
            if self._fail.get(p, 0) < 2:
                return p
        return None

    def report_failure(self, proxy: str | None) -> None:
        if proxy:
            self._fail[proxy] = self._fail.get(proxy, 0) + 1

    def report_success(self, proxy: str | None) -> None:
        if proxy:
            self._fail[proxy] = 0

    def __len__(self) -> int:
        return len(self._proxies)


_POOL: ProxyPool | None = None


def proxy_pool() -> ProxyPool:
    """进程内单例：失败计数跨任务累积，避免每个任务都把坏代理试一遍。"""
    global _POOL
    if _POOL is None:
        _POOL = ProxyPool()
    return _POOL


def reset_for_tests() -> None:
    global _POOL
    _POOL = None
