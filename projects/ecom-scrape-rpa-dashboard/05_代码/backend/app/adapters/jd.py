"""京东适配器（T06 / D-16）。

真实模式：search.jd.com 搜索页（商品卡 data-sku 属性 + 内嵌 JSON 价格）。
MOCK_MODE=1 时 URL 指向本地 mock_site——同一套 L2 链路（令牌桶/UA/观测），
换真站点只改 base_url 判定，下游不动（L10 / Mock 红线）。
"""
from __future__ import annotations

from urllib.parse import quote

from app.adapters.base import BaseAdapter


class JdAdapter(BaseAdapter):
    platform = "jd"
    real_domain = "search.jd.com"

    def list_url(self, keyword: str, page: int) -> str:
        if self._is_mock_base():
            return f"{self.base_url()}/list?platform=jd&keyword={quote(keyword)}&page={page}"
        return f"https://search.jd.com/Search?keyword={quote(keyword)}&page={2 * page - 1}"
