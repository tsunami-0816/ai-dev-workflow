#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""解析 JMeter JTL（CSV），输出吞吐/P95/P99/错误率，写入 reports/jmeter_summary.json。"""
import csv
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def summarize(path):
    elapsed, codes, start, end = [], [], None, None
    with open(path, encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            elapsed.append(int(row["elapsed"]))
            codes.append(row["responseCode"])
            ts = int(row["timeStamp"])
            start = ts if start is None else min(start, ts)
            end = ts + int(row["elapsed"]) if end is None else max(end, ts + int(row["elapsed"]))
    wall = max((end - start) / 1000.0, 0.001)
    errors = sum(1 for c in codes if not c.startswith("2"))
    elapsed_sorted = sorted(elapsed)

    def pct(p):
        idx = int(round(p / 100 * (len(elapsed_sorted) - 1)))
        return elapsed_sorted[min(len(elapsed_sorted) - 1, idx)]

    return {"file": path.name, "samples": len(elapsed), "wall_s": round(wall, 2),
            "tps": round(len(elapsed) / wall, 1),
            "avg_ms": round(statistics.mean(elapsed), 2),
            "p95_ms": pct(95), "p99_ms": pct(99), "max_ms": max(elapsed),
            "error_rate": round(errors / len(elapsed), 6) if elapsed else 1}


def main():
    files = [Path(a) for a in sys.argv[1:]] or [ROOT / "result.jtl"]
    out = [summarize(f) for f in files]
    dest = ROOT.parent / "reports" / "jmeter_summary.json"
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    for item in out:
        print(json.dumps(item, ensure_ascii=False))
    print(f"写入 {dest}")


if __name__ == "__main__":
    main()
