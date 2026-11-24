"""采集编排（L1/L2/L3 / T02、T07~T10 / D-04~D-08、D-23~D-28）。

核心纪律（P0-01）：本模块只写 stg_price_item / task_run_item / task_run.cursor，
绝不写 price_snapshot——价格表唯一写入口在 clean/pipeline.py（ADR-10）。
页级事务：stg + item + cursor 三件事同事务（D-23），断电宁重不漏；
重启续采以 item 表计数为准自愈（cursor 与 item 不一致时记 WARN 并按 item 修正）。
"""
from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from app import db
from app.adapters.base import BaseAdapter, FetchContext
from app.adapters.registry import concurrency_slot, get_adapter
from app.config import Targets, load_targets, log_event, now_cn, settings, site_cfg, today_cn

# ---------------------------------------------------------------- SQL（页级事务专用）
# stg 幂等 upsert：唯一键 (run_id, platform, sku_id)，重跑同页只更新不新增（D-28 / T10）
STG_UPSERT_SQL = (
    "INSERT INTO stg_price_item "
    "(run_id, platform, sku_id, title, shop, url, url_hash, raw_price_text, price, "
    " raw_sales_text, sales_num, captured_date, crawled_at) "
    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
    "ON DUPLICATE KEY UPDATE title=VALUES(title), shop=VALUES(shop), url=VALUES(url), "
    "url_hash=VALUES(url_hash), raw_price_text=VALUES(raw_price_text), price=VALUES(price), "
    "raw_sales_text=VALUES(raw_sales_text), sales_num=VALUES(sales_num), "
    "crawled_at=VALUES(crawled_at)"
)
ITEM_UPSERT_SQL = (
    "INSERT INTO task_run_item (run_id, platform, sku_id, status, reason, at) "
    "VALUES (%s,%s,%s,%s,%s,%s) "
    "ON DUPLICATE KEY UPDATE status=VALUES(status), reason=VALUES(reason), at=VALUES(at)"
)


class CollectLockError(Exception):
    """第二个采集进程并发启动：文件锁拒绝，退出码 4（§8 并发边界，D-83）。"""


@dataclass
class RunSummary:
    platform: str
    task_id: int
    run_id: int
    status: str
    pages: int = 0
    items: int = 0
    cursor: dict = field(default_factory=dict)


# ---------------------------------------------------------------- 文件锁（D-83 单入口）
class _FileLock:
    """采集单入口约束：令牌桶是进程内单例，两个采集进程会绕过限速（C03 破防），
    所以用锁文件在进程间互斥；崩溃残留锁由 mtime 兜底过期。"""

    def __init__(self, path: Path):
        self._path = path

    def __enter__(self):
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if self._path.exists():
            age = now_cn().timestamp() - self._path.stat().st_mtime
            if age < 3600:
                raise CollectLockError(f"已有采集进程在运行（锁文件 {self._path}，{int(age)}s 前）")
            self._path.unlink()  # 1 小时前的残留锁视为崩溃残留
        fd = os.open(self._path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        return self

    def __exit__(self, *exc):
        try:
            self._path.unlink()
        except OSError:
            pass
        return False


# ---------------------------------------------------------------- task/task_run（L1）
def ensure_task(platform: str, targets: Targets) -> dict:
    """task upsert + config_hash 版本化：配置变了 version+1（D-03 / T01）。"""
    name = f"daily_{platform}"
    rows = db.query(
        "SELECT id, config_hash, version FROM task WHERE name=%(n)s ORDER BY version DESC LIMIT 1",
        {"n": name},
        pool="rw",
    )
    config_hash = targets.config_hash
    if not rows:
        task_id = db.execute(
            "INSERT INTO task (name, platform, cron, config_hash, version) "
            "VALUES (%s,%s,%s,%s,1)",
            (name, platform, targets.freq_cron, config_hash),
        )
        return {"id": task_id, "version": 1, "changed": True}
    row = rows[0]
    if row["config_hash"] != config_hash:
        # 配置变更 → 新版本行（保留历史版本可审计，uk_task_name_version 保证唯一）
        task_id = db.execute(
            "INSERT INTO task (name, platform, cron, config_hash, version) "
            "VALUES (%s,%s,%s,%s,%s)",
            (name, platform, targets.freq_cron, config_hash, int(row["version"]) + 1),
        )
        return {"id": task_id, "version": int(row["version"]) + 1, "changed": True}
    return {"id": row["id"], "version": int(row["version"]), "changed": False}


def start_run(task_id: int, cursor: dict | None = None) -> int:
    return db.execute(
        "INSERT INTO task_run (task_id, status, `cursor`, started_at) VALUES (%s,'running',%s,%s)",
        (task_id, json.dumps(cursor or {"page": 0, "offset": 0, "done": 0}), now_cn()),
    )


def _finish_run(run_id: int, status: str, cursor: dict, snapshot_cnt: int, error: str | None = None) -> None:
    db.execute(
        "UPDATE task_run SET status=%s, `cursor`=%s, snapshot_cnt=%s, finished_at=%s, error=%s "
        "WHERE id=%s",
        (status, json.dumps(cursor), snapshot_cnt, now_cn(), error[:1000] if error else None, run_id),
    )


# ---------------------------------------------------------------- 页级事务（T08 / D-23）
def commit_page(adapter_platform: str, run_id: int, page: int, items, captured_date) -> int:
    """单事务三件事：stg upsert + task_run_item upsert + cursor 前进。

    先落暂存再推游标：断电时宁重一页、不漏一页（R-07）。
    坏 SKU（解析失败的）不进 stg（脏到无法解析），只落 item status=fail 不阻塞整页（D-27）。
    """
    ok_items = [(it, it.sku_id and it.title) for it in items]
    with db.transaction() as conn:
        with conn.cursor() as cur:
            for it, ok in ok_items:
                if ok:
                    cur.execute(STG_UPSERT_SQL, it.to_stg_row(run_id, captured_date))
                    cur.execute(ITEM_UPSERT_SQL, (run_id, it.platform, it.sku_id, "ok", None, it.crawled_at))
                else:
                    # 坏 SKU：脏到无法解析的不进 stg，只记 fail，不阻塞整页（D-27）
                    cur.execute(
                        ITEM_UPSERT_SQL,
                        (run_id, it.platform, it.sku_id or "_unknown", "fail", "parse_incomplete", it.crawled_at),
                    )
            cur.execute("SELECT COUNT(*) c FROM task_run_item WHERE run_id=%s AND status='ok'", (run_id,))
            done = cur.fetchone()["c"]
            cur.execute("SELECT `cursor` FROM task_run WHERE id=%s FOR UPDATE", (run_id,))
            prev = json.loads(cur.fetchone()["cursor"] or "{}")
            cursor = {
                "page": max(page, int(prev.get("page", 0))),
                "offset": done,
                "done": done,
            }
            cur.execute("UPDATE task_run SET `cursor`=%s WHERE id=%s", (json.dumps(cursor), run_id))
    return sum(1 for _, ok in ok_items if ok)


# ---------------------------------------------------------------- 主编排（T02）
async def run_collect(
    platform: str,
    captured_date: date | None = None,
    force: bool = False,
) -> RunSummary:
    s = settings()
    if platform in s.disable_platforms:
        # D-08 降级开关：某平台挂了不影响其他平台出数
        log_event("collect", level="warn", event="PLATFORM_DISABLED", platform=platform)
        raise SystemExit(0)
    captured = captured_date or today_cn()
    targets = load_targets()
    tp = next((t for t in targets.platforms if t.platform == platform), None)
    if tp is None:
        raise ValueError(f"targets.yaml 未配置平台 {platform}")

    with _FileLock(s.data_dir / "collect.lock"):
        task = ensure_task(platform, targets)
        run_id = start_run(task["id"])
        log_event("collect", event="RUN_START", platform=platform, run_id=run_id,
                  task_version=task["version"], config_changed=task["changed"],
                  captured_date=str(captured), mock_mode=s.mock_mode)

        ctx = FetchContext(run_id=run_id, captured_date=captured, force=force)
        adapter = get_adapter(platform, ctx)
        cfg = site_cfg(platform)
        page_size = int(cfg.get("page_size", 30))
        total_pages = max(1, -(-tp.expect_sku // page_size))  # ceil

        summary = RunSummary(platform=platform, task_id=task["id"], run_id=run_id, status="ok")
        items_cnt = 0
        empty_pages = 0
        try:
            tasks = []
            sem = concurrency_slot(platform)
            for page in range(1, total_pages + 1):
                kw = tp.keywords[(page - 1) % len(tp.keywords)]

                async def _page(p=page, k=kw):
                    async with sem:
                        return await adapter.fetch_list(k, p)

                tasks.append(asyncio.create_task(_page()))
            for page_no, fut in enumerate(tasks, start=1):
                result = await fut
                if result.blocked or (result.http_status is not None and result.http_status >= 400):
                    empty_pages += 1
                    log_event("collect", level="warn", event="PAGE_BLOCKED",
                              platform=platform, run_id=run_id, page=page_no,
                              status=result.http_status)
                    continue
                if not result.items:
                    empty_pages += 1
                    continue
                items_cnt += commit_page(platform, run_id, page_no, result.items, captured)
                summary.pages += 1
            await adapter.aclose()

            status = "ok" if empty_pages == 0 else "partial"
            summary.items = items_cnt
            summary.status = status
            summary.cursor = {"page": summary.pages, "offset": items_cnt, "done": items_cnt}
            _finish_run(run_id, status, summary.cursor, items_cnt)
            log_event("collect", event="RUN_DONE", platform=platform, run_id=run_id,
                      status=status, pages=summary.pages, items=items_cnt)
            return summary
        except (KeyboardInterrupt, asyncio.CancelledError):
            # 中断：游标停在已提交页，续采 cli resume 从下一页开始（D-25）
            _finish_run(run_id, "interrupted",
                        {"page": summary.pages, "offset": items_cnt, "done": items_cnt},
                        items_cnt, error="interrupted")
            raise
        except Exception as e:
            _finish_run(run_id, "failed", {"page": summary.pages, "offset": items_cnt,
                                            "done": items_cnt}, items_cnt,
                        error=f"{type(e).__name__}: {e}")
            log_event("collect", level="error", event="RUN_FAILED", platform=platform,
                      run_id=run_id, error=str(e)[:500])
            raise


async def resume_collect(run_id: int) -> RunSummary:
    """断点续采（T09 / D-25）：从 cursor.page 的下一页继续；
    done 计数与 item 表不一致时以 item 表为准（自愈，R-07）。"""
    rows = db.query(
        "SELECT r.id, r.status, r.`cursor`, r.task_id, t.platform FROM task_run r "
        "JOIN task t ON t.id=r.task_id WHERE r.id=%(i)s",
        {"i": run_id}, pool="rw",
    )
    if not rows:
        raise ValueError(f"run_id={run_id} 不存在")
    row = rows[0]
    cursor = json.loads(row["cursor"] or "{}")
    real_done = db.query(
        "SELECT COUNT(*) c FROM task_run_item WHERE run_id=%s AND status='ok'",
        {"r": run_id}, pool="rw",
    )[0]["c"]
    if int(cursor.get("done", 0)) != int(real_done):
        # 自愈而非报错：item 表是唯一事实源（ADR-05）
        log_event("collect", level="warn", event="CURSOR_SELF_HEAL", run_id=run_id,
                  cursor_done=cursor.get("done"), item_count=real_done)
        db.execute("UPDATE task_run SET `cursor`=%s WHERE id=%s",
                   (json.dumps({**cursor, "done": real_done, "offset": real_done}), run_id))
    captured = today_cn()
    stg = db.query(
        "SELECT captured_date FROM stg_price_item WHERE run_id=%(r)s LIMIT 1", {"r": run_id},
        pool="rw",
    )
    if stg:
        captured = stg[0]["captured_date"]

    db.execute("UPDATE task_run SET status='running' WHERE id=%s", (run_id,))
    targets = load_targets()
    platform = row["platform"]
    tp = next((t for t in targets.platforms if t.platform == platform), None)
    if tp is None:
        raise ValueError(f"targets.yaml 未配置平台 {platform}")
    s = settings()

    with _FileLock(s.data_dir / "collect.lock"):
        cfg = site_cfg(platform)
        page_size = int(cfg.get("page_size", 30))
        total_pages = max(1, -(-tp.expect_sku // page_size))
        ctx = FetchContext(run_id=run_id, captured_date=captured, force=False)
        adapter = get_adapter(platform, ctx)
        start_page = int(cursor.get("page", 0)) + 1  # 下一页，已提交页不重采（uk 兜底防重）
        items_cnt = int(real_done)
        pages_done = int(cursor.get("page", 0))
        empty_pages = 0
        try:
            for page in range(start_page, total_pages + 1):
                kw = tp.keywords[(page - 1) % len(tp.keywords)]
                result = await adapter.fetch_list(kw, page)
                if result.blocked or (result.http_status is not None and result.http_status >= 400):
                    empty_pages += 1
                    continue
                if not result.items:
                    empty_pages += 1
                    continue
                items_cnt += commit_page(platform, run_id, page, result.items, captured)
                pages_done = page
            await adapter.aclose()
            status = "ok" if empty_pages == 0 else "partial"
            cur = {"page": pages_done, "offset": items_cnt, "done": items_cnt}
            _finish_run(run_id, status, cur, items_cnt)
            log_event("collect", event="RESUME_DONE", run_id=run_id, platform=platform,
                      status=status, items=items_cnt, from_page=start_page)
            return RunSummary(platform=platform, task_id=row["task_id"], run_id=run_id,
                              status=status, pages=pages_done, items=items_cnt, cursor=cur)
        except (KeyboardInterrupt, asyncio.CancelledError):
            _finish_run(run_id, "interrupted", {"page": pages_done, "offset": items_cnt,
                                                "done": items_cnt}, items_cnt, error="interrupted")
            raise
        except Exception as e:
            _finish_run(run_id, "failed", {"page": pages_done, "offset": items_cnt,
                                            "done": items_cnt}, items_cnt,
                        error=f"{type(e).__name__}: {e}")
            raise
