"""拼多多适配器（T06 / D-18）。

移动端页面（mobile.yangkeduo.com）：ua_pool 按 platform=mobile 自动切窄屏 UA，
与目标页面指纹一致。
"""
from __future__ import annotations

from urllib.parse import quote

from app.adapters.base import BaseAdapter


class PddAdapter(BaseAdapter):
    platform = "pdd"
    real_domain = "mobile.yangkeduo.com"
    mobile = True

    def list_url(self, keyword: str, page: int) -> str:
        if self._is_mock_base():
            return f"{self.base_url()}/list?platform=pdd&keyword={quote(keyword)}&page={page}"
        return f"https://mobile.yangkeduo.com/search_result.html?search_key={quote(keyword)}&page={page}"
