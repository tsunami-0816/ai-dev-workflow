#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第 8 步性能测试（Python 主压测 + JMeter 交叉复核的 Python 侧）。

用法：python perf_test.py [--duration 10] [--concurrency 10,20,50] [--booking-samples 30]
输出：reports/perf_result.json + 控制台表格
"""
import argparse
import json
import statistics
import sys
import threading
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from api.cloud_api import proxy_action  # noqa: E402
from common.config_loader import load_config  # noqa: E402
from common.data_util import days_from_today, idem_key, next_phone  # noqa: E402
from common.request_util import ApiClient  # noqa: E402
from common.sql_util import Mysql  # noqa: E402
from common.redis_util import Redis  # noqa: E402


def percentile(values, p):
    if not values:
        return 0
    ordered = sorted(values)
    k = max(0, min(len(ordered) - 1, int(round((p / 100) * (len(ordered) - 1)))))
    return ordered[k]


def one_request(url, timeout=10):
    started = time.time()
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            body = resp.read()
            ok = resp.status == 200 and b'"code":0' in body
        return (time.time() - started) * 1000, ok
    except Exception:
        return (time.time() - started) * 1000, False


def run_tier(base_url, path, concurrency, duration):
    url = base_url.rstrip("/") + path
    latencies, errors = [], 0
    lock = threading.Lock()

    def worker():
        nonlocal errors
        end = time.time() + duration
        while time.time() < end:
            ms, ok = one_request(url)
            with lock:
                latencies.append(ms)
                if not ok:
                    errors += 1

    threads = [threading.Thread(target=worker) for _ in range(concurrency)]
    started = time.time()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    wall = time.time() - started
    total = len(latencies)
    return {
        "concurrency": concurrency,
        "duration_s": round(wall, 2),
        "samples": total,
        "tps": round(total / wall, 1) if wall else 0,
        "avg_ms": round(statistics.mean(latencies), 1) if latencies else 0,
        "p50_ms": round(percentile(latencies, 50), 1),
        "p95_ms": round(percentile(latencies, 95), 1),
        "max_ms": round(max(latencies), 1) if latencies else 0,
        "error_rate": round(errors / total, 4) if total else 1.0,
    }


def booking_p95(cfg, samples):
    """C03：预约端到端 P95（云函数 8093 → 后端 8092），样本 ≥ 20。"""
    cf = ApiClient(cfg["cf_url"], name="perf-cf")
    account = cfg["accounts"]["demo"]
    session = proxy_action(cf, "login", {"account": account["account"],
                                         "password": account["password"]})
    token = session.data()["token"]
    mysql = Mysql(cfg["mysql"])
    redis = Redis(cfg["redis"]["host"], cfg["redis"]["port"])
    date = days_from_today(21)
    phones, latencies, errors = [], [], 0
    try:
        for i in range(samples):
            phone = next_phone()
            phones.append(phone)
            body = {"action": "createBooking", "payload": {
                "packageId": 1, "bookDate": date, "slot": ("上午", "下午", "晚间")[i % 3],
                "contact": phone, "remark": "perf"}, "token": token}
            started = time.time()
            resp = cf.post("/", body, timeout=15)
            latencies.append((time.time() - started) * 1000)
            if resp.status != 200 or resp.code() != 0:
                errors += 1
            if i < 3:
                print(f"[perf booking warmup] {resp.status} {resp.elapsed_ms}ms")
    finally:
        rows = mysql.query("SELECT id FROM booking WHERE contact IN ("
                           + ",".join(mysql.quote(p) for p in phones) + ")")
        ids = [r[0] for r in rows]
        if ids:
            mysql.execute(f"DELETE FROM notify_log WHERE booking_id IN ({','.join(ids)})")
            mysql.execute(f"DELETE FROM booking WHERE id IN ({','.join(ids)})")
        for i, phone in enumerate(phones):
            redis.delete(idem_key(phone, date, ("上午", "下午", "晚间")[i % 3]))
    return {
        "samples": samples,
        "avg_ms": round(statistics.mean(latencies), 1),
        "p50_ms": round(percentile(latencies, 50), 1),
        "p95_ms": round(percentile(latencies, 95), 1),
        "max_ms": round(max(latencies), 1),
        "error_rate": round(errors / samples, 4),
        "path": "POST 8093 apiProxy createBooking → 8092 /api/bookings",
        "threshold_p95_ms": 800,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration", type=int, default=10)
    parser.add_argument("--concurrency", default="10,20,50")
    parser.add_argument("--booking-samples", type=int, default=30)
    parser.add_argument("--read-path", default="/api/packages?page=1&size=10")
    args = parser.parse_args()

    cfg = load_config()
    print(f"perf base={cfg['base_url']} cf={cfg['cf_url']}")
    tiers = [int(x) for x in args.concurrency.split(",") if x.strip()]
    results = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
               "target": args.read_path, "tiers": []}
    for tier in tiers:
        stats_ = run_tier(cfg["base_url"], args.read_path, tier, args.duration)
        results["tiers"].append(stats_)
        print(f"tier={tier:>2} tps={stats_['tps']:>7} avg={stats_['avg_ms']:>6}ms "
              f"p95={stats_['p95_ms']:>7}ms err={stats_['error_rate']:.2%}")

    if args.booking_samples > 0:
        booking = booking_p95(cfg, args.booking_samples)
        results["booking_p95"] = booking
        print(f"C03 booking P95={booking['p95_ms']}ms avg={booking['avg_ms']}ms "
              f"err={booking['error_rate']:.2%}")

    out_dir = ROOT / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "perf_result.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"结果已写入 {out}")
    failed = any(t["error_rate"] > 0 for t in results["tiers"]) or \
        (results.get("booking_p95", {}).get("error_rate", 0) > 0)
    return 1 if failed else 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
