"""UA 轮换与 Header 模板（L2 / T03 / D-10）。

固定 header 顺序：真实浏览器头顺序稳定，乱序本身是机器人指纹（架构 §3 L2 第 2 步）。
10 条真实 UA 轮换；Cookie/口令永不写进代码（Mock 红线/合规红线）。
"""
from __future__ import annotations

import itertools
import threading

# 近年 Chrome / Edge / 移动端主流 UA（每平台取相近期版本，覆盖窄屏 pdd 移动端场景 D-18）
_UAS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Mobile Safari/537.36",
]

_MOBILE_PLATFORMS = {"pdd", "douyin"}  # 拼多多/抖音移动端页面指纹（D-18/D-19）

_cycle = itertools.cycle(range(len(_UAS)))
_lock = threading.Lock()


def pick(platform: str) -> str:
    """轮换取 UA；移动端平台优先取移动 UA（窄屏指纹与目标页面一致）。"""
    with _lock:
        idx = next(_cycle)
    if platform in _MOBILE_PLATFORMS:
        return _UAS[7 + (idx % 3)]
    return _UAS[idx % 7]


def headers_template(platform: str, referer: str = "") -> dict:
    """固定顺序的请求头模板（dict 有序 → httpx 按插入顺序发送）。"""
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
        "User-Agent": pick(platform),
    }
    if referer:
        headers["Referer"] = referer
    return headers
