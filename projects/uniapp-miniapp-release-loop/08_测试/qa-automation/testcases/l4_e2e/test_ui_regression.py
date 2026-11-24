#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""L4/UI：浏览器回归 Q-020（我的列表滚到底）与 Q-025（长说明展开/收起）。

数据全部由 pytest 造、pytest 清；浏览器脚本只负责操作与断言，证据落 08_测试/evidence/。
"""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from common.data_util import days_from_today

QA = Path(__file__).resolve().parents[2]
PROJECT = QA.parents[1]
FRONTEND = PROJECT / "05_代码" / "frontend"
UI_DIR = QA / "ui"

CACHE_KEY = "ub:pkg:list"

pytestmark = [pytest.mark.l4, pytest.mark.ui]


@pytest.fixture(scope="session")
def h5_up(cfg):
    from common.request_util import ApiClient
    resp = ApiClient(cfg["h5_url"], name="h5-ui").get("/", headers={"Accept": "text/html"}, timeout=10)
    assert resp.status == 200, f"H5 5186 未就绪：{resp.status}（先起 dev:h5）"
    assert shutil.which("node"), "node 未安装"
    assert (FRONTEND / "node_modules" / "puppeteer-core").exists(), "puppeteer-core 未安装"
    assert Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe").exists(), "Edge 不存在"
    return cfg["h5_url"]


def _run_ui(script, env_extra, timeout=120):
    env = dict(os.environ)
    env["NODE_PATH"] = str(FRONTEND / "node_modules")
    env.update(env_extra)
    proc = subprocess.run(["node", str(UI_DIR / script)], cwd=str(FRONTEND), env=env,
                          capture_output=True, text=True, encoding="utf-8", errors="replace",
                          timeout=timeout)
    out = (proc.stdout or "").strip()
    err = (proc.stderr or "").strip()
    assert proc.returncode == 0, f"{script} 失败\nstdout={out[-2000:]}\nstderr={err[-2000:]}"
    last = [line for line in out.splitlines() if line.strip().startswith("{")][-1]
    return json.loads(last)


def test_my_list_scroll_pagination(bookings, h5_up):
    """Q-020：造 25 单 → 首屏 20 → 滚到底追加到 25（≥2 个分页请求）。"""
    date = days_from_today(20)
    for i in range(25):
        resp, _ = bookings.create(package_id=1, book_date=date,
                                  slot=("上午", "下午", "晚间")[i % 3])
        assert resp.status == 200 and resp.code() == 0, resp.text[:200]
    result = _run_ui("my_pagination.cjs", {"H5_URL": h5_up, "EXPECT_MIN": "25"})
    assert result["pass"], result
    assert result["firstCount"] == 20, result
    assert result["afterCount"] >= 25, result


def test_long_summary_fold_branch(cfg, redis, mysql, h5_up):
    """Q-025：临时造 >52 字说明套餐 → 详情页出现「展开」→ 点后变「收起」。"""
    long_summary = "这是一段用于验证折叠分支的长说明：" + "灯" * 70
    assert len(long_summary) > 52
    try:
        mysql.execute("DELETE FROM package WHERE id=9001")
        mysql.execute(
            "INSERT INTO package (id,title,price,cover_url,tags,summary,sort,status) VALUES "
            f"(9001,'长说明临时套餐',99.00,'/static/covers/cover-1.jpg','测试',"
            f"'{long_summary}',999,1)")
        redis.delete(CACHE_KEY)
        from common.request_util import ApiClient
        assert ApiClient(cfg["base_url"], name="fixture").get("/api/packages/9001").status == 200

        result = _run_ui("fold.cjs", {"H5_URL": h5_up, "PKG_ID": "9001"})
        assert result["pass"], result
        assert result["before"]["foldText"] == "展开"
        assert result["after"]["foldText"] == "收起"
        assert result["before"]["summaryLen"] > 52
    finally:
        mysql.execute("DELETE FROM package WHERE id=9001")
        redis.delete(CACHE_KEY)
