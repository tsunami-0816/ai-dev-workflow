"""统一数据结构（架构 §2.4 models.py）。

L2 解析输出、L5 清洗输入共用的 8 字段统一结构（platform/sku_id/title/price/
sales_tag/shop/url/crawled_at）+ 暂存双列（raw_price_text / raw_sales_text 原文保留，
P0-01：脏值原文进 stg，清洗时才有依据拦截）。
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional


@dataclass
class RawItem:
    """适配器输出的统一商品行（8 字段口径，架构 §3 L2 第 9 步）。"""

    platform: str
    sku_id: str
    title: str
    shop: str = ""
    url: str = ""
    url_hash: str = ""
    raw_price_text: str = ""     # 原文，如 '¥1,299.00' / '面议'（进 stg 供清洗复核）
    price: Optional[float] = None  # 解析值；脏值为 None——绝不能在这里编造价格（ADR-06）
    raw_sales_text: str = ""     # 如 '1.3万+人付款'
    sales_num: Optional[int] = None
    crawled_at: datetime = field(default_factory=datetime.now)

    def to_stg_row(self, run_id: int, captured_date) -> tuple:
        """stg_price_item 幂等 upsert 的参数元组（T10 / D-28）。"""
        return (
            run_id,
            self.platform,
            self.sku_id,
            (self.title or "")[:255] or None,
            (self.shop or "")[:128] or None,
            (self.url or "")[:512] or None,
            self.url_hash or None,
            (self.raw_price_text or "")[:64] or None,
            self.price,
            (self.raw_sales_text or "")[:64] or None,
            self.sales_num,
            captured_date,
            self.crawled_at,
        )

    def as_dict(self) -> dict:
        return asdict(self)
