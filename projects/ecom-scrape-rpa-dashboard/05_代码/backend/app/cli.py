"""CLI 入口（T02 / D-05~D-08、D-25、D-38、D-82）。

子命令：initdb / wait-db / collect / backfill / resume / clean / report / rpa / prune / check-config
退出码：0 成功；1 运行时错误；2 配置非法（不发任何请求）；3 外部工具缺失（可降级）；
4 采集锁冲突（第二个采集进程，D-83）。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime

from app import db
from app.config import ConfigError, log_event, settings


def _load_all_configs() -> None:
    """T01 强校验：任何命令执行前先校验配置，错了直接退出码 2。"""
    from app.config import load_sites, load_targets

    load_targets()
    load_sites()


def cmd_initdb(args) -> int:
    """建库建表建账号建分区（D-05）：幂等，可重复执行。"""
    sql_path = db._SQL_DIR / "init" / "01_schema.sql"
    text = sql_path.read_text(encoding="utf-8")
    stmts = db.split_statements(text)
    with db._pool("root").borrow() as conn:
        with conn.cursor() as cur:
            for stmt in stmts:
                cur.execute(stmt)
        conn.commit()
    for stmt in db.create_accounts():
        db.execute(stmt, pool="root")
    alters = db.ensure_partitions()
    tables = db.query("SHOW TABLES", pool="root")
    print(json.dumps({
        "event": "initdb", "ok": True, "tables": len(tables),
        "accounts": ["ecom_ro", "ecom_rw"],
        "partition_alters": len(alters),
        "table_names": sorted(list(t["Tables_in_ecom_scrape"] for t in tables)),
    }, ensure_ascii=False))
    return 0


def cmd_wait_db(args) -> int:
    try:
        db.wait_db(timeout=args.timeout)
    except db.DbNotReady as e:
        print(f"DB 未就绪: {e}", file=sys.stderr)
        return 1
    print("db ready")
    return 0


def cmd_collect(args) -> int:
    from app.jobs.collect_job import run_collect

    async def _go():
        if args.platform == "all":
            results = []
            for p in ("jd", "tmall", "pdd", "douyin"):
                if p in settings().disable_platforms:
                    continue
                results.append(await run_collect(p))
            return results
        return [await run_collect(args.platform)]

    date = None
    if args.date:
        date = datetime.strptime(args.date, "%Y-%m-%d").date()
    summaries = asyncio.run(_go())
    print(json.dumps([s.__dict__ for s in summaries], ensure_ascii=False, default=str))
    return 0


def cmd_backfill(args) -> int:
    """补采（D-07）：漏跑日期可补，不重不漏（stg 唯一键 + URL 指纹去重兜底）。"""
    from app.jobs.collect_job import run_collect

    date = datetime.strptime(args.date, "%Y-%m-%d").date()
    platforms = [args.platform] if args.platform != "all" else ["jd", "tmall", "pdd", "douyin"]
    out = []
    for p in platforms:
        out.append(asyncio.run(run_collect(p, captured_date=date)))
    print(json.dumps([s.__dict__ for s in out], ensure_ascii=False, default=str))
    return 0


def cmd_resume(args) -> int:
    from app.jobs.collect_job import resume_collect

    summary = asyncio.run(resume_collect(args.run_id))
    print(json.dumps(summary.__dict__, ensure_ascii=False, default=str))
    return 0


def cmd_clean(args) -> int:
    from app.clean.pipeline import run_clean

    date = datetime.strptime(args.date, "%Y-%m-%d").date() if args.date else None
    report = run_clean(date)
    print(json.dumps(report, ensure_ascii=False, default=str))
    return 0


def cmd_report(args) -> int:
    from app.jobs.report_job import run_report

    date = datetime.strptime(args.date, "%Y-%m-%d").date() if args.date else None
    out = run_report(date)
    print(json.dumps(out, ensure_ascii=False, default=str))
    return 0


def cmd_rpa(args) -> int:
    from app.rpa.engine import run_flow

    out = run_flow(args.flow, inject_fault=args.inject_fault, keyword=args.keyword)
    print(json.dumps(out, ensure_ascii=False, default=str))
    return 0


def cmd_prune(args) -> int:
    from app.jobs import prune

    out = prune.run(days=args.days, dry_run=args.dry_run)
    print(json.dumps(out, ensure_ascii=False))
    return 0


def cmd_check_config(args) -> int:
    from app.config import load_sites, load_targets

    t = load_targets()
    s = load_sites()
    print(json.dumps({
        "ok": True,
        "config_hash": t.config_hash,
        "platforms": [p.platform for p in t.platforms],
        "sites": sorted(s["sites"].keys()),
    }, ensure_ascii=False))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="app.cli", description="ecom-scrape-rpa-dashboard CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("initdb", help="建库/14 表/账号/分区")
    p.set_defaults(func=cmd_initdb)
    p.add_argument("--ensure-partitions", action="store_true")

    p = sub.add_parser("wait-db", help="等待 MySQL 就绪")
    p.add_argument("--timeout", type=int, default=60)
    p.set_defaults(func=cmd_wait_db)

    p = sub.add_parser("collect", help="采集（--platform mock|jd|tmall|pdd|douyin|all）")
    p.add_argument("--platform", required=True)
    p.add_argument("--date", help="补采指定日 YYYY-MM-DD")
    p.add_argument("--force", action="store_true", help="忽略 URL 指纹去重强制重抓")
    p.set_defaults(func=cmd_collect)

    p = sub.add_parser("backfill", help="按日期补采")
    p.add_argument("--date", required=True)
    p.add_argument("--platform", default="all")
    p.set_defaults(func=cmd_backfill)

    p = sub.add_parser("resume", help="断点续采")
    p.add_argument("--run-id", type=int, required=True)
    p.set_defaults(func=cmd_resume)

    p = sub.add_parser("clean", help="清洗当日（或指定日）stg → price_snapshot")
    p.add_argument("--date", default=None)
    p.set_defaults(func=cmd_clean)

    p = sub.add_parser("report", help="生成 Excel 日报")
    p.add_argument("--date", default=None)
    p.set_defaults(func=cmd_report)

    p = sub.add_parser("rpa", help="执行 RPA 流程")
    p.add_argument("--flow", default="jd_price_scan")
    p.add_argument("--inject-fault", default=None, help="selector: 注入选择器故障（C08 取证）")
    p.add_argument("--keyword", default="避孕套 超薄")
    p.set_defaults(func=cmd_rpa)

    p = sub.add_parser("prune", help="数据保留清理（默认 dry-run）")
    p.add_argument("--days", type=int, default=30)
    p.add_argument("--dry-run", action="store_true", default=True)
    p.add_argument("--execute", dest="dry_run", action="store_false")
    p.set_defaults(func=cmd_prune)

    p = sub.add_parser("check-config", help="仅校验配置")
    p.set_defaults(func=cmd_check_config)

    args = parser.parse_args(argv)

    try:
        _load_all_configs()
    except ConfigError as e:
        # 配置非法：退出码 2，不发起任何请求（T01 验收标准）
        print(f"[CONFIG_ERROR] {e}", file=sys.stderr)
        return 2

    from app.jobs.collect_job import CollectLockError

    try:
        return args.func(args)
    except CollectLockError as e:
        print(f"[COLLECT_LOCKED] {e}", file=sys.stderr)
        return 4
    except db.DbNotReady as e:
        print(f"[DB_NOT_READY] {e}", file=sys.stderr)
        log_event("alert", level="error", rule="db_not_ready", detail=str(e)[:300])
        return 1
    except SystemExit as e:
        return int(e.code or 0)
    except Exception as e:  # noqa: BLE001 —— CLI 兜底：错误摘要给终端，堆栈进日志
        import traceback

        log_event("alert", level="error", rule="cli_uncaught", cmd=args.cmd,
                  detail=f"{type(e).__name__}: {e}"[:300])
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
