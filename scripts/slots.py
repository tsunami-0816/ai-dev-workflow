# -*- coding: utf-8 -*-
"""生产并行调度看板（3 槽：2 生成 + 1 运行/验收）。

只读队列与各项目看板，不改任何状态。输出 projects/_生产并行看板.md
用法：py -3.11 slots.py [--slots 3] [--run 1]

槽位含义：
  运行/验收槽（run）：同一时刻只允许 1 个，起服务、跑浏览器、要人工走查的都在这里
  生成槽（gen）：写文档/写代码，不长期占端口，允许 2 个并行
"""
import argparse
import re
import sys
from pathlib import Path

ROOT = Path(r"D:\lg\project\工作流测试")
QUEUE = ROOT / "WORKFLOW_项目队列.md"
PROJ = ROOT / "projects"
QUEUE_DIR = PROJ / "_队列"
OUT = PROJ / "_生产并行看板.md"

HUMAN_HINT = ("待用户", "人工", "卡在人工", "验收", "安全", "拍板", "方向稿")
RUN_HINT = ("第 6 步", "第 7 步", "第 8", "第 9 步", "冒烟", "联调", "验收")

# 能力簇覆盖 JD 数（来源：resume/_S1等项目审计.md，2026-11-22）
G_COVER = {"G9": 8, "G8": 5, "G10": 4, "G2": 4, "G12": 3, "G14": 3, "G1": 2, "G16": 2,
           "G4": 2, "G6": 2, "G15": 2, "G13": 1, "G18": 1, "G19": 1, "G20": 1,
           "G21": 1, "G7": 1, "G3": 1, "G5": 0, "G17": 1}
RE_G = re.compile(r"G\d+")


def cover(r):
    """一个项目能解锁的 JD 数：取来源字段里所有 G 号的覆盖数之和（去重）。"""
    gs = set(RE_G.findall(r.get("source", "")) + RE_G.findall(r.get("desc", "")))
    return sum(G_COVER.get(g, 0) for g in gs)



def parse_queue():
    rows = []
    for line in QUEUE.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if len(cells) < 9:
            continue
        name = cells[0].replace("`", "").strip()
        if not name or name in ("项目名",) or set(name) <= set("-: "):
            continue
        rows.append(dict(name=name, route=cells[1], desc=cells[2], design=cells[3],
                         status=cells[4], source=cells[5], start=cells[6],
                         done=cells[7], block=cells[8]))
    return rows


def board(name):
    p = PROJ / name / "_项目状态.md"
    if not p.exists():
        return {}
    t = p.read_text(encoding="utf-8", errors="ignore")
    d = {}
    m = re.search(r"- 当前阶段：\*\*(.+?)\*\*", t) or re.search(r"- 当前阶段：(.+)", t)
    d["stage"] = m.group(1).strip() if m else ""
    m = re.search(r"- 总体状态：(.+)", t)
    d["state"] = m.group(1).strip() if m else ""
    m = re.search(r"- \*\*下一步动作\*\*：\*\*(.+?)\*\*", t) or re.search(r"- 下一步动作：\*\*(.+?)\*\*", t) or re.search(r"- \*\*下一步动作\*\*：(.+)", t)
    d["next"] = m.group(1).strip() if m else ""
    m = re.search(r"- 必读文件：(.+)", t)
    d["read"] = m.group(1).strip() if m else ""
    return d


def human_blocked(b):
    """只认「当前阶段」里的卡点词。不拼 state/next：模板占位文本会污染判定。"""
    st = b.get("stage", "")
    return any(h in st for h in ("待用户", "人工", "卡在人工", "验收", "拍板", "方向稿"))


def _read_tier():
    log = PROJ / "_生产运行日志.md"
    if not log.exists():
        return 1
    tier = 1
    for line in log.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if len(cells) >= 2 and cells[1] in ("1", "2", "3"):
            tier = int(cells[1])
    return tier


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier", type=int, choices=[1, 2, 3], default=None,
                    help="覆盖档位：1 串行 / 2 双工位 / 3 三工位；缺省读运行日志最后一条")
    ap.add_argument("--archive", action="store_true", help="同时归档到 projects/_看板归档/<日期>.md")
    args = ap.parse_args()
    tier = args.tier or _read_tier()
    args.slots = {1: 1, 2: 2, 3: 3}[tier]
    args.run = 1

    rows = parse_queue()
    doing = [r for r in rows if r["status"].startswith("进行中")]
    todo = [r for r in rows if r["status"] == "待开工"]
    shelved = [r for r in rows if "搁置" in r["status"]]
    done = [r for r in rows if r["status"].startswith("已完成") or "豁免" in r["status"]]

    inflight = []
    for r in doing:
        b = board(r["name"])
        r["b"] = b
        r["blocked"] = human_blocked(b)
        r["run"] = any(k in b.get("stage", "") for k in RUN_HINT)
        inflight.append(r)

    slot_run = [r for r in inflight if r["run"]][: args.run]
    slot_gen_doing = [r for r in inflight if not r["run"] and not r["blocked"]][: args.slots - args.run]
    need_gen = args.slots - args.run - len(slot_gen_doing)
    todo_sorted = sorted(todo, key=lambda r: (-cover(r), r["name"]))
    slot_gen_new = todo_sorted[: max(0, need_gen)]

    L = []
    L.append("# 生产并行看板")
    L.append("")
    L.append(f"> 自动生成 · {args.slots} 槽（{args.run} 运行 + {args.slots - args.run} 生成）· 档位 tier={tier} · 只读，不改状态")
    L.append(f"> 队列：进行中 {len(doing)} / 待开工 {len(todo)} / 已搁置 {len(shelved)} / 已完成 {len(done)}")
    L.append("")

    L.append("## 今日槽位")
    L.append("")
    i = 0
    for r in slot_run:
        i += 1
        b = r["b"]
        L.append(f"### 槽 {chr(64 + i)} · 运行/验收 · `{r['name']}`")
        L.append(f"- 当前阶段：{b.get('stage', '-')}")
        L.append(f"- 下一步：{b.get('next', '读看板接续')}")
        L.append(f"- 占用：端口 + 内存（本槽同一时刻只跑 1 套服务）")
        L.append("")
    for r in slot_gen_doing:
        i += 1
        b = r["b"]
        L.append(f"### 槽 {chr(64 + i)} · 生成 · `{r['name']}`（进行中）")
        L.append(f"- 当前阶段：{b.get('stage', '-')}")
        L.append(f"- 下一步：{b.get('next', '读看板接续')}")
        L.append("")
    for r in slot_gen_new:
        i += 1
        has_design = (QUEUE_DIR / r["name"] / "00_项目设计书.md").exists()
        L.append(f"### 槽 {chr(64 + i)} · 生成 · `{r['name']}`（待开工）")
        L.append(f"- 设计书：{'在 `_队列/`' if has_design else '缺失，不能开工'}")
        L.append(f"- 能解锁 JD：**{cover(r)}** 个（来源 `{r['source'][:40]}`）")
        L.append(f"- 开工命令：`wf init {r['name']}`")
        L.append("")

    blocked = [r for r in inflight if r["blocked"]]
    if blocked:
        L.append("## 待你 1 分钟（人工卡点，其他人都能继续跑）")
        L.append("")
        for r in blocked:
            L.append(f"- **{r['name']}**：{r['b'].get('stage', '')}")
            L.append(f"  - 你要做：{r['b'].get('next', r['block'])[:120]}")
        L.append("")

    auto = [r for r in inflight if not r["blocked"]]
    L.append("## 不用你、自动推进")
    L.append("")
    if auto:
        for r in auto:
            L.append(f"- `{r['name']}`：{r['b'].get('stage', '-')}")
    else:
        L.append("- 无（现有项目都在人工点上）")
    L.append("")

    L.append("## 资源规则")
    L.append("")
    L.append("1. 运行/验收槽只有 1 个：起服务、跑浏览器、占端口的都在这里排队，不并行。")
    L.append(f"2. 生成槽 {args.slots - args.run} 个：只写文档和代码，不起长期服务；每轮切项目只读该项目 `_项目状态.md`。")
    L.append("3. 任一槽做完一步跑机器闸门；报红就地修，不跨槽借资源。")
    L.append("4. 人工卡点全部集中到「待你 1 分钟」一节，一次答完，不逐个打断。")
    L.append("")

    OUT.write_text("\n".join(L), encoding="utf-8")
    if args.archive:
        ARCH = PROJ / "_看板归档"
        ARCH.mkdir(parents=True, exist_ok=True)
        from datetime import datetime
        ap_ = ARCH / f"{datetime.now().strftime('%Y-%m-%d_%H%M')}.md"
        ap_.write_text("\n".join(L) + "\n", encoding="utf-8")
        print(f"archived {ap_}")
    print(f"wrote {OUT}")
    print(f"doing={len(doing)} todo={len(todo)} run_slot={len(slot_run)} gen_slot={len(slot_gen_doing) + len(slot_gen_new)}")


if __name__ == "__main__":
    sys.exit(main())
