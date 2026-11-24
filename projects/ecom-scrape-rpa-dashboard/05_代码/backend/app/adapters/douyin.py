"""抖音适配器（T06 / D-19）。

只取公开字段（公开榜单/商城页）；登录墙出现即 302 判定 blocked=login_redirect，
不重试登录（合规红线：不碰账号安全策略），转 RPA 低频补采或人工兜底。
"""
from __future__ import annotations

from urllib.parse import quote

from app.adapters.base import BaseAdapter


class DouyinAdapter(BaseAdapter):
    platform = "douyin"
    real_domain = "haohuo.jinritemai.com"
    mobile = True

    def list_url(self, keyword: str, page: int) -> str:
        if self._is_mock_base():
            return f"{self.base_url()}/list?platform=douyin&keyword={quote(keyword)}&page={page}"
        return f"https://haohuo.jinritemai.com/views/search?keyword={quote(keyword)}&page={page}"
