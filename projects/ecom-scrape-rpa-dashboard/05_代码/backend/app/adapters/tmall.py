"""天猫适配器（T06 / D-17）。

真实模式：list.tmall.com 搜索页，必须 Cookie；空池走 none 路径（cookie_state=none），
观测里可见，由 mock 兜底（R-02：无真实账号不阻塞其他链路）。
"""
from __future__ import annotations

from urllib.parse import quote

from app.adapters.base import BaseAdapter


class TmallAdapter(BaseAdapter):
    platform = "tmall"
    real_domain = "list.tmall.com"

    def list_url(self, keyword: str, page: int) -> str:
        if self._is_mock_base():
            return f"{self.base_url()}/list?platform=tmall&keyword={quote(keyword)}&page={page}"
        return f"https://list.tmall.com/search_product.htm?q={quote(keyword)}&page={page}"
