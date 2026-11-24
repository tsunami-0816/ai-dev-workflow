"""本地 mock 站点（L10 / T31 / D-84、D-85）。

替代真实电商站点（外部依赖）：3+1 平台列表/详情页 + 分页 + 内嵌 JSON；
可选注入 429 / 验证码页 / 脏数据（反爬与清洗能力的触发器，D-85）。
MOCK: 替代 jd/tmall/pdd/douyin 真实站点；上线前 MOCK_MODE=0 + 真实 Cookie 即切换。
数据确定性：价格 = hash(platform, sku, date) 派生 → 同日同值、跨日有涨跌，
top-changes / trend / 突变检测因此可离线复现。
端口 5190，仅 127.0.0.1（§5.3 网络边界）。
"""
from __future__ import annotations

import hashlib
from datetime import date

from fastapi import FastAPI, Query, Response
from fastapi.responses import HTMLResponse

app = FastAPI(title="ecom mock site", docs_url=None, redoc_url=None)

PLATFORMS = ["jd", "tmall", "pdd", "douyin", "mock"]
PAGE_SIZE = 30
SKU_PER_PLATFORM = 120  # ≥100，C01 断言下限

TITLE_WORDS = {
    "jd": ["杰士邦零感超薄", "杜蕾斯air空气感", "岡本002薄透", "极薄003隐形", "持久延时经典"],
    "tmall": ["【官方旗舰店】超薄套装", "【包邮】玻尿酸润滑", "秒杀大颗粒螺纹", "尊享组合装", "热感浮点"],
    "pdd": ["特价批发家用装", "拼团超值12只", "工厂直发基础款", "百亿补贴精选", "实惠装30只"],
    "douyin": ["直播间同款超薄", "达人推荐组合", "新品尝鲜装", "热卖爆款", "达人专属折扣"],
    "mock": ["通用超薄样品", "通用组合装", "通用基础款", "通用尝鲜装", "通用实惠装"],
}
SHOPS = {
    "jd": "京东自营", "tmall": "天猫旗舰", "pdd": "拼多多家工厂店", "douyin": "抖in好物", "mock": "mock自营",
}


def _h(*parts: str) -> int:
    return int(hashlib.sha1(":".join(parts).encode("utf-8")).hexdigest()[:8], 16)


def _price_of(platform: str, sku: str, d: date) -> float:
    """确定性价格：base(20~300) + 当日扰动(-10~+10)。跨日变化支撑环比与突变。"""
    base = 20 + _h(platform, sku, "base") % 280
    wiggle = _h(platform, sku, str(d)) % 21 - 10
    return round(float(base + wiggle) + 0.9, 2)


def gen_items(platform: str, d: date, inject: str = "") -> list[dict]:
    if platform not in PLATFORMS:
        return []
    out = []
    words = TITLE_WORDS[platform]
    for i in range(SKU_PER_PLATFORM):
        sku = f"{platform[:2]}{100000 + i * 7}"
        price_val = _price_of(platform, sku, d)
        # 每 20 个混 1 个脏价格（面议/--）：清洗拦截率的日常信号源；inject=dirty 加密脏比例
        if inject == "dirty" and i % 3 == 0:
            price_text = "面议" if i % 2 == 0 else "0"
        elif i % 20 == 5:
            price_text = "面议"
        elif i % 20 == 13:
            price_text = "--"
        else:
            price_text = f"¥{price_val:,.2f}"
        sales_text = "1.3万+人付款" if i % 3 == 0 else (
            f"{3200 + (i % 7) * 111}+人付款" if i % 3 == 1 else "--"
        )
        out.append({
            "sku_id": sku,
            "title": f"{words[i % len(words)]} {i + 1}号 【限时特价】全角ＴＥＳＴ",
            "shop": SHOPS[platform],
            "price_text": price_text,
            "price": price_val,
            "sales_text": sales_text,
            "url": f"/detail?platform={platform}&sku={sku}",
        })
    return out


def _render_html(platform: str, items: list[dict], page: int, total_pages: int) -> str:
    import json as _json

    cards = "\n".join(
        f'<div class="item-card" data-sku="{it["sku_id"]}">'
        f'<a class="title" href="{it["url"]}">{it["title"]}</a>'
        f'<span class="price">{it["price_text"]}</span>'
        f'<span class="sales">{it["sales_text"]}</span>'
        f'<span class="shop">{it["shop"]}</span></div>'
        for it in items
    )
    # 内嵌 JSON：与真实站点「页面带 window 数据」的结构对齐，适配器同一条解析路径
    payload = _json.dumps({"items": items}, ensure_ascii=False)
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>mock {platform} page {page}</title></head>
<body><div id="search-list">{cards}</div>
<script type="application/json" id="items-data">{payload}</script>
<div class="pager">page {page}/{total_pages}</div></body></html>"""


@app.get("/health")
def health():
    return {"ok": True, "env": "mock"}


@app.get("/list", response_class=HTMLResponse)
def list_page(
    platform: str = Query(...),
    page: int = Query(1, ge=1),
    date: str = Query(""),
    inject: str = Query("", description="429 / captcha / dirty"),
):
    d = date and _parse(date) or _today()
    if platform not in PLATFORMS:
        return Response(status_code=404)
    if inject == "429" and page == 2:
        # D-85：注入限流 → 反爬层走长冷却 30s 分支（可观测验证）
        return Response(status_code=429)
    if inject == "captcha" and page == 3:
        # D-85：注入验证码页（假 200）→ 启发式识别必须判 blocked（D-21）
        return HTMLResponse("<html><body>亲，请完成下方验证码后继续访问</body></html>")
    items = gen_items(platform, d, inject)
    total_pages = -(-len(items) // PAGE_SIZE)
    start = (page - 1) * PAGE_SIZE
    return HTMLResponse(_render_html(platform, items[start:start + PAGE_SIZE], page, total_pages))


@app.get("/detail", response_class=HTMLResponse)
def detail(platform: str = Query(...), sku: str = Query(...), date: str = Query("")):
    d = date and _parse(date) or _today()
    if platform not in PLATFORMS:
        return Response(status_code=404)
    items = [it for it in gen_items(platform, d) if it["sku_id"] == sku]
    if not items:
        return Response(status_code=404)
    return HTMLResponse(_render_html(platform, items, 1, 1))


def _today() -> date:
    from datetime import datetime

    return datetime.now().date()


def _parse(s: str) -> date:
    from datetime import datetime

    return datetime.strptime(s, "%Y-%m-%d").date()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=5190, log_level="warning")
