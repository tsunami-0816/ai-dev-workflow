"""mock 适配器（T31 / D-84 / L10）。

platform=mock：显式走本地 mock_site（127.0.0.1:5190），走与真实站点完全相同的
L2 路径（同样过令牌桶与观测）——「换真站点只换 adapter」的证明件。
MOCK: 替代真实外部站点依赖；上线前 targets.yaml 改回真实平台 + MOCK_MODE=0 即切换。
"""
from __future__ import annotations

from urllib.parse import quote

from app.adapters.base import BaseAdapter


class MockAdapter(BaseAdapter):
    platform = "mock"
    real_domain = "127.0.0.1"

    def list_url(self, keyword: str, page: int) -> str:
        return f"{self.base_url()}/list?platform=mock&keyword={quote(keyword)}&page={page}"
