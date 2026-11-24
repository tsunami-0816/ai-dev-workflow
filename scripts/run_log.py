# -*- coding: utf-8 -*-
"""生产运行日志：每次推进留一行，供以后回溯与算 KPI。

用法：
  py -3.11 run_log.py add --slot B --project rn-mobile-app-release --step 1 \
      --product 01_项目基线说明书.md --gate "step_gate_check --step 1" --exit 0 --minutes 25

  py -3.11 run_log.py tail -n 20
  py -3.11 run_log.py kpi
  py -3.11 run_log.py set-tier --tier 2 --note "期1看板验证通过，进双工位"

日志：projects/_生产运行日志.md（表头不存在时自动创建）
"""
import argparse
import re
import sys
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

PROJ = Path(r"D:\lg\project\工作流测试\projects")
LOG = PROJ / "_生产运行日志.md"

HEADER = """# 生产运行日志

> 每推进一步追加一行；**没有日志行的推进视为没发生**（`WORKFLOW_项目队列.md` 产能规则）。
> 表头固定 12 列，追加写、不改旧行；要纠正错误就新写一行并在「备注」里写"更正第 N 行"。
> 档位：1=串行 1｜2=双工位（1 运行+1 生成）｜3=三工位（1 运行+2 生成）

| 时间 | 档位 | 工位 | 项目 | 步骤 | 动作 | 产物 | 闸门 | 退出码 | 耗时(分) | 结果 | 备注 |
|---|---|---|---|---|---|---|---|---|---|---|---|
"""


def ensure():
    if not LOG.exists():
        LOG.parent.mkdir(parents=True, exist_ok=True)
        LOG.write_text(HEADER, encoding="utf-8")


def rows():
    if not LOG.exists():
        return []
    out = []
    for line in LOG.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if len(cells) < 12 or cells[0] in ("时间",) or set(cells[0]) <= set("-: "):
            continue
        out.append(cells)
    return out


def read_tier():
    rs = rows()
    if not rs:
        return 1
    for r in reversed(rs):
        if r[1] in ("1", "2", "3"):
            return int(r[1])
    return 1


def cmd_add(a):
    ensure()
    if a.exit == 0:
        result = "通过"
    elif a.exit == 2:
        result = "脚本错"
    else:
        result = "报红"
    if a.result:
        result = a.result
    tier = a.tier if a.tier is not None else read_tier()
    t = datetime.now().strftime("%Y-%m-%d %H:%M")
    cells = [t, str(tier), a.slot or "-", a.project, str(a.step or "-"), a.action,
             (a.product or "-").replace("|", "／"), (a.gate or "-").replace("|", "／"),
             str(a.exit) if a.exit is not None else "-", str(a.minutes or "-"), result,
             (a.note or "-").replace("|", "／").replace("\n", " ")]
    with LOG.open("a", encoding="utf-8") as f:
        f.write("| " + " | ".join(cells) + " |\n")
    print(f"已追加：{t} 档位{tier} {a.slot or '-'} {a.project} 第{a.step}步 → {result}")


def cmd_tail(a):
    ensure()
    data = LOG.read_text(encoding="utf-8").splitlines()
    print("\n".join(data[-a.n:]))


def cmd_set_tier(a):
    ensure()
    t = datetime.now().strftime("%Y-%m-%d %H:%M")
    cells = [t, str(a.tier), "-", "-", "-", "切换档位", "-", "-", "-", "-", "通过", a.note or "-"]
    with LOG.open("a", encoding="utf-8") as f:
        f.write("| " + " | ".join(cells) + " |\n")
    print(f"档位已切到 {a.tier}：{a.note or ''}")


def cmd_kpi(a):
    rs = rows()
    if not rs:
        print("日志为空，先跑 add。")
        return
    today = date.today().isoformat()
    # 工具/脚本类改动不算项目产出（project 填 workflow-cli 的行只用于留痕追溯）
    OFF_PROJECT = {"-", "", "workflow-cli"}

    # 1) 今日产出
    today_rows = [r for r in rs if r[0].startswith(today)]
    today_projects = {r[3] for r in today_rows if r[3] not in OFF_PROJECT}
    today_steps = {r[3] + "#" + r[4] for r in today_rows if r[5] in ("推进", "完成步骤")}

    # 2) 单项目耗时（分钟和）
    proj_minutes = defaultdict(float)
    for r in rs:
        if r[3] in OFF_PROJECT:
            continue
        try:
            proj_minutes[r[3]] += float(r[9])
        except Exception:
            pass

    # 3) 门禁首轮通过率：每个 (项目, 步骤) 第一次的退出码
    first = {}
    for r in rs:
        if r[3] in OFF_PROJECT:
            continue
        if r[7] in ("-", "") or r[8] in ("-", ""):
            continue
        k = (r[3], r[4], r[7])
        if k not in first:
            first[k] = r[8]
    passed = sum(1 for v in first.values() if v == "0")
    rate = (passed / len(first) * 100) if first else 0

    print(f"## KPI 快照（{today}）\n")
    print(f"- 今日推进项目数：**{len(today_projects)}**（{('、'.join(sorted(today_projects)) or '无')}）")
    print(f"- 今日推进步骤数：**{len(today_steps)}**")
    print(f"- 门禁首轮通过率：**{rate:.0f}%**（{passed}/{len(first)} 个「项目×步骤×闸门」首次通过）")
    print(f"- 单项目累计耗时（分钟）：")
    for k, v in sorted(proj_minutes.items(), key=lambda kv: -kv[1]):
        if k == "-":
            continue
        print(f"  - {k}：{v:.0f} 分钟 ≈ {v / 60:.2f} 天")
    print(f"\n红线：单项目 >2.5 天，或首轮通过率 <60% → 降一档。")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("add")
    p.add_argument("--slot", default="-", help="工位 A/B/C")
    p.add_argument("--project", required=True)
    p.add_argument("--step", default="-")
    p.add_argument("--action", default="推进")
    p.add_argument("--product", default="-")
    p.add_argument("--gate", default="-")
    p.add_argument("--exit", type=int, default=None)
    p.add_argument("--minutes", type=float, default=None)
    p.add_argument("--result", default=None, help="不填按退出码推导")
    p.add_argument("--note", default="-")
    p.add_argument("--tier", type=int, default=None)
    p.set_defaults(func=cmd_add)

    p = sub.add_parser("tail")
    p.add_argument("-n", type=int, default=20)
    p.set_defaults(func=cmd_tail)

    p = sub.add_parser("set-tier")
    p.add_argument("--tier", type=int, required=True, choices=[1, 2, 3])
    p.add_argument("--note", default="-")
    p.set_defaults(func=cmd_set_tier)

    p = sub.add_parser("kpi")
    p.set_defaults(func=cmd_kpi)

    a = ap.parse_args()
    a.func(a)


if __name__ == "__main__":
    sys.exit(main())
