"""归一化（L5 / T15 / D-39）。

价格/销量/标题归一在「适配器解析」与「清洗」两处共用同一组函数：
口径必须同源，否则 stg.price 与清洗结果会漂移（ADR-08 同理）。
脏值（面议/--/空）解析为 None——绝不在解析层编造价格（ADR-06）。
"""
from __future__ import annotations

import re
import unicodedata

# 价格：¥1,299.00 / 1299元 / 1,299 / 1299.00 → float
_PRICE_RE = re.compile(r"(\d+(?:,\d{3})*(?:\.\d+)?)")
# 销量：1.3万+人付款 / 5万+ / 3200+人付款 / 3200 → int
_SALES_WAN_RE = re.compile(r"(\d+(?:\.\d+)?)\s*万")
_SALES_PLAIN_RE = re.compile(r"(\d+)")

# 标题营销词（架构 §3 L5 第 1 步）：【】包裹块、包邮/秒杀/官方旗舰店等
_TITLE_BRACKET_RE = re.compile(r"【[^】]*】")
_MARKETING_WORDS = ("包邮", "秒杀", "官方旗舰店", "限时特价", "正品促销", "折扣")


def parse_price(text: str | None) -> float | None:
    """'¥1,299.00'/'1299元'/'1,299' → 1299.0；'面议'/'--'/'' → None（脏值不违约）。"""
    if not text:
        return None
    m = _PRICE_RE.search(str(text))
    if not m:
        return None
    try:
        return round(float(m.group(1).replace(",", "")), 2)
    except ValueError:
        return None


def parse_sales(text: str | None) -> int | None:
    """'1.3万+人付款' → 13000；'3200+人付款' → 3200；'--' → None。"""
    if not text:
        return None
    text = str(text)
    m = _SALES_WAN_RE.search(text)
    if m:
        return int(float(m.group(1)) * 10000)
    m = _SALES_PLAIN_RE.search(text)
    if m:
        return int(m.group(1))
    return None


def sales_unit(text: str | None) -> str | None:
    """枚举校验用：'万' / '件' / None（L5 第 5 步 enum 规则的输入）。"""
    if not text:
        return None
    t = str(text)
    if "万" in t:
        return "万"
    if "件" in t or "人付款" in t or "人已买" in t:
        return "件"
    return None


def normalize_title(title: str | None) -> str:
    """标题归一：去【】营销块与营销词 + 全半角统一 + 连续空白折叠。"""
    if not title:
        return ""
    t = str(title)
    t = _TITLE_BRACKET_RE.sub("", t)
    for w in _MARKETING_WORDS:
        t = t.replace(w, "")
    # 全角→半角（NFKC 会顺带统一各类兼容字符）
    t = unicodedata.normalize("NFKC", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def normalize_price_text(text: str | None) -> float | None:
    """清洗侧别名（pandas apply 用），与适配器解析同源。"""
    return parse_price(text)
