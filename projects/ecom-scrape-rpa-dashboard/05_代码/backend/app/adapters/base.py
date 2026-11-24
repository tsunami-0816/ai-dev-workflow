"""适配器基类：L2 请求主链路的唯一实现（T05 / D-15、D-20~D-22）。

所有站点适配器共用这条链路，换站点只换 adapter 的 URL/解析配置，下游不动（D-15）：
  令牌桶 → UA/header 模板 → Cookie 池 → 代理池 → httpx（connect 5s/read 10s，
  follow_redirects=False 以识别 302 登录页）→ 风控判定 → 观测落表 → raw_page 快照。
URL 指纹去重：url_hash = sha1(去 utm/track 参数后规范化的 URL)（D-22）。
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx
from parsel import Selector

from app import db
from app.antibot import backoff, cookie_pool, proxy_pool, rate_limiter
from app.antibot.observability import detect_block, record_metric
from app.clean.normalize import parse_price, parse_sales
from app.config import ConfigError, now_cn, settings, site_cfg
from app.models import RawItem

# 采集 UA 统一 track 参数剔除集合（utm_* 与常见埋点参数）
_TRACK_PARAMS = re.compile(r"^(utm_|track|spm|scm|psid|abcCache|union_)")


def url_fingerprint(url: str) -> str:
    """URL 指纹：去 utm/track 参数、剩余参数排序 → sha1（D-22，同 URL 不重复请求）。"""
    parts = urlsplit(url)
    q = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
         if not _TRACK_PARAMS.match(k)]
    canonical = urlunsplit((parts.scheme, parts.netloc.lower(), parts.path, urlencode(sorted(q)), ""))
    return hashlib.sha1(canonical.encode("utf-8")).hexdigest()


@dataclass
class FetchContext:
    """一次采集运行 的上下文。"""

    run_id: Optional[int] = None
    captured_date: Optional[date] = None
    force: bool = False  # True 时忽略 url 指纹去重（补采/强制重抓）


@dataclass
class PageResult:
    items: list[RawItem] = field(default_factory=list)
    url: str = ""
    url_hash: str = ""
    http_status: Optional[int] = None
    blocked: bool = False
    from_cache: bool = False  # 命中 URL 指纹去重，未出网


class BaseAdapter:
    platform = "base"
    # 真实域名（限速域）；mock 模式下自动指向本地 mock_site（Mock 红线：不依赖真实账号）
    real_domain = "www.example.com"
    mobile = False

    def __init__(self, ctx: FetchContext):
        self.ctx = ctx
        self.cfg = site_cfg(self.platform)
        self._client: httpx.AsyncClient | None = None
        self._client_proxy: str | None = None

    # ------------------------------------------------------------ URL
    def base_url(self) -> str:
        s = settings()
        if s.mock_mode == 1 or self.platform == "mock":
            # MOCK: 替代真实站点域名。上线前将 MOCK_MODE=0 并保证 config/cookies 就位，
            # 适配器自动切换到 real_domain（同一套解析与反爬链路，无需改代码）。
            return s.mock_site_url.rstrip("/")
        return f"https://{self.real_domain}"

    def list_url(self, keyword: str, page: int) -> str:
        raise NotImplementedError

    def _is_mock_base(self) -> bool:
        b = self.base_url()
        return b.startswith("http://127.0.0.1") or "localhost" in b

    # ------------------------------------------------------------ 请求链路（L2）
    def _timeout(self) -> httpx.Timeout:
        t = self.cfg.get("timeout", {})
        return httpx.Timeout(connect=float(t.get("connect", 5)), read=float(t.get("read", 10)),
                             write=10.0, pool=5.0)

    async def _client_(self, proxy: str | None) -> httpx.AsyncClient:
        # httpx 0.27 代理挂在客户端上；代理切换（D-12 失败切换）时重建客户端
        if self._client is not None and proxy != self._client_proxy:
            await self.aclose()
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self._timeout(),
                follow_redirects=False,  # 302→登录页必须在应用层判定（D-21）
                http2=False,             # 与浏览器一致的 HTTP/1.1 指纹面（§1.1）
                proxies={"http://": proxy, "https://": proxy} if proxy else None,
            )
            self._client_proxy = proxy
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def request(self, url: str, referer: str = "") -> tuple[Optional[str], Optional[int], bool]:
        """完整 L2 链路：返回 (html or None, http_status, blocked)。

        每次尝试（含重试）各写一行 antibot_metrics——C02 分母含重试（§10.1）。
        限速门在「发送前一刻」过（见 rate_limiter 模块注释：客户端构建耗时
        不能挤占下一个槽位，否则实测间隔 < 1/qps，C03 破防）。
        """
        domain = urlsplit(url).netloc
        qps = float(self.cfg["rate"]["qps"])

        headers = self._headers(referer)
        cookie_header, cookie_state = cookie_pool.acquire(self.platform)
        if cookie_header:
            headers["Cookie"] = cookie_header
        proxy = proxy_pool.proxy_pool().pick()
        via_proxy = bool(proxy)

        client = await self._client_(proxy)
        last_status: Optional[int] = None
        for retry_no in range(backoff.MAX_RETRIES):
            wait_ms = await rate_limiter.gate(domain, qps)  # 发送前一刻限速（含重试各自过门）
            at = now_cn()
            try:
                resp = await client.get(url, headers=headers)
            except httpx.HTTPError:
                # 网络错误 → 指数退避 1s×2^n；记 http_status=0 供失败率统计（§7）
                record_metric(platform=self.platform, url=url, http_status=None, latency_ms=0,
                              wait_ms=wait_ms, via_proxy=via_proxy, cookie_state=cookie_state,
                              retry_no=retry_no, run_id=self.ctx.run_id, at=at)
                proxy_pool.proxy_pool().report_failure(proxy)
                await backoff_sleep(backoff.delay_for_network_error(retry_no))
                last_status = None
                continue

            latency_ms = int((now_cn() - at).total_seconds() * 1000)
            status = resp.status_code
            last_status = status
            text = resp.text
            blocked, reason = detect_block(status, dict(resp.headers), text)
            record_metric(platform=self.platform, url=url, http_status=status,
                          latency_ms=latency_ms, wait_ms=wait_ms, via_proxy=via_proxy,
                          cookie_state=cookie_state, blocked_flag=blocked,
                          block_reason=reason, retry_no=retry_no,
                          run_id=self.ctx.run_id, at=at)
            proxy_pool.proxy_pool().report_success(proxy)

            if status in (301, 302) and "login" in str(resp.headers.get("location", "")).lower():
                cookie_pool.mark_invalid(self.platform)  # Cookie 失效剔除（D-11）

            cooldown = backoff.cooldown_for_status(status)
            if cooldown is not None:
                # 429/503 → 长冷却 30s，不走普通退避（被限流时短退避等于硬闯）
                await backoff_sleep(cooldown)
                continue
            if blocked:
                break  # 风控页不重试：换 UA/Cookie/代理/RPA 是调度层动作（L2 降级链）
            if status is not None and 200 <= status < 300:
                return text, status, blocked
            if backoff.is_retryable_status(status):
                await backoff_sleep(backoff.delay_for_network_error(retry_no))
                continue
            break
        return None, last_status, True

    def _headers(self, referer: str) -> dict:
        from app.antibot import ua_pool

        if not referer:
            referer = self.base_url() + "/"
        return ua_pool.headers_template(self.platform, referer=referer)

    # ------------------------------------------------------------ 快照与去重
    def _raw_path(self, url_hash: str) -> "tuple[bool, str]":
        d = self.ctx.captured_date or now_cn().date()
        folder = settings().raw_dir / self.platform / d.strftime("%Y%m%d")
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{url_hash}.html"
        return path.exists(), str(path)

    def _already_fetched_today(self, url_hash: str) -> Optional[str]:
        """URL 指纹去重：当日已有同指纹快照 → 直接复用文件，省一次出网（D-22）。"""
        if self.ctx.force:
            return None
        rows = db.query(
            "SELECT body_path FROM raw_page WHERE url_hash=%(h)s AND crawled_at >= %(d)s LIMIT 1",
            {"h": url_hash, "d": str(self.ctx.captured_date or now_cn().date())},
        )
        return rows[0]["body_path"] if rows else None

    def _persist_raw(self, url: str, url_hash: str, text: str, status: int) -> str:
        _, path = self._raw_path(url_hash)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        db.execute(
            "INSERT INTO raw_page (platform, url, url_hash, body_path, content_type, "
            "http_status, byte_size, run_id, crawled_at) "
            "VALUES (%(p)s, %(u)s, %(h)s, %(b)s, %(ct)s, %(s)s, %(sz)s, %(r)s, %(t)s)",
            dict(p=self.platform, u=url[:512], h=url_hash, b=path, ct="text/html",
                 s=status, sz=len(text.encode("utf-8")), r=self.ctx.run_id, t=now_cn()),
        )
        return path

    async def fetch_list(self, keyword: str, page: int) -> PageResult:
        url = self.list_url(keyword, page)
        url_hash = url_fingerprint(url)
        result = PageResult(url=url, url_hash=url_hash)

        cached_path = self._already_fetched_today(url_hash)
        if cached_path:
            try:
                with open(cached_path, encoding="utf-8") as f:
                    result.items = self.parse_list(f.read())
                result.from_cache = True
                return result
            except OSError:
                pass  # 文件丢失则重新出网（快照文件不作为唯一事实源）

        html, status, blocked = await self.request(url)
        if html is None or blocked:
            return result
        result.http_status = status
        self._persist_raw(url, url_hash, html, status or 0)
        result.items = self.parse_list(html)
        return result

    # ------------------------------------------------------------ 解析（parsel）
    def parse_list(self, html: str) -> list[RawItem]:
        """两段式：优先内嵌 JSON（结构与 mock_site/详情页 window 数据一致），
        否则走 sites.yaml 配置的 CSS 选择器（真实站点路径，R-01 用快照回归）。"""
        items = self._parse_embedded_json(html)
        if items is not None:
            return items
        return self._parse_css(html)

    def _parse_embedded_json(self, html: str) -> Optional[list[RawItem]]:
        sel = Selector(html)
        node = sel.css('script#items-data[type="application/json"]::text').get()
        if not node:
            return None
        try:
            data = json.loads(node)
        except json.JSONDecodeError:
            return None
        out = []
        for it in data.get("items", []):
            out.append(self.to_item(it))
        return out

    def _parse_css(self, html: str) -> list[RawItem]:
        sels = self.cfg.get("selectors") or {}
        if not sels.get("item"):
            return []
        sel = Selector(html)
        out: list[RawItem] = []
        for node in sel.css(sels["item"]):
            raw = {
                "sku_id": (node.attrib.get(sels.get("sku_attr", "data-sku")) or "").strip(),
                "title": (node.css(sels.get("title", "") + "::text").get() or "").strip(),
                "price": (node.css(sels.get("price", "") + "::text").get() or "").strip(),
                "sales": (node.css(sels.get("sales", "") + "::text").get() or "").strip(),
                "shop": (node.css(sels.get("shop", "") + "::text").get() or "").strip(),
                "url": (node.css(sels.get("url", "") + "::attr(href)").get() or "").strip(),
            }
            if not raw["sku_id"] or not raw["title"]:
                continue
            out.append(self.normalize_row(raw))
        return out

    def to_item(self, it: dict) -> RawItem:
        """内嵌 JSON → RawItem（mock_site 与 RPA extract 输出同构，直接复用）。"""
        return self.normalize_row({
            "sku_id": str(it.get("sku_id", "")),
            "title": str(it.get("title", "")),
            "price": str(it.get("price_text", it.get("price", ""))),
            "sales": str(it.get("sales_text", "")),
            "shop": str(it.get("shop", "")),
            "url": str(it.get("url", "")),
        })

    def normalize_row(self, raw: dict) -> RawItem:
        price = parse_price(raw["price"])
        url = raw["url"]
        if url and not url.startswith("http"):
            url = self.base_url() + url
        return RawItem(
            platform=self.platform,
            sku_id=raw["sku_id"][:64],
            title=raw["title"],
            shop=raw.get("shop", "")[:128],
            url=url[:512],
            url_hash=url_fingerprint(url) if url else "",
            raw_price_text=raw["price"][:64] if raw["price"] else None,
            price=price,
            raw_sales_text=raw.get("sales")[:64] if raw.get("sales") else None,
            sales_num=parse_sales(raw.get("sales", "")),
            crawled_at=now_cn(),
        )


async def backoff_sleep(seconds: float) -> None:
    import asyncio

    await asyncio.sleep(seconds)
