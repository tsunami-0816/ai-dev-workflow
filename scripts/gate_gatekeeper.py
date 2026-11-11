#!/usr/bin/env python3
"""
新闸观察期管理器（G1/G8 · 2026-11-11；方案 §8 回退策略落地）

解决的问题：新闸默认旁路观察期，不能一直挂在观察期没人转硬闸。
本脚本在 step10 复盘 / step11 体检时跑，按项目观察日志自动判定：
  - 本项目该闸无误报 → 观察计数 +1；达到 threshold_projects → 自动翻 strict 硬闸；
  - 出现误报（R12 人工确认脚本误判）→ 计数清零、误报累计，继续观察期；
  - 本项目没跑过该闸 → 不计观察，不误转。

用法：
  python scripts/gate_gatekeeper.py status
  python scripts/gate_gatekeeper.py review <项目目录>
  python scripts/gate_gatekeeper.py mark-fp <项目目录> --gate input_card --note "路径含括号被误判越界"

闸口状态文件：workflow/gate_states.yaml；项目观察日志：<项目根>/.gate_observations/<gate>.jsonl。
退出码：0 正常；2 脚本自身错误（目录不存在 / 参数错）。
"""

import argparse
import sys
from pathlib import Path

import _gate_states as gates  # noqa: E402


def _force_utf8_output():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def cmd_status(_args) -> int:
    states = gates.load_states()
    cfg_gates = states.get("gates", {})
    if not cfg_gates:
        print("⚠️ gate_states.yaml 无闸口登记（或文件读不到，按全旁路处理）")
        return 0
    for name, cfg in cfg_gates.items():
        status = cfg.get("status", "observe")
        obs = cfg.get("observed_projects", 0)
        thr = cfg.get("threshold_projects", 1)
        fp = cfg.get("false_positives", 0)
        act = cfg.get("activated_at") or "—"
        print(f"{cfg.get('display', name)} [{name}] 状态={status} "
              f"观察 {obs}/{thr} 误报 {fp} 激活于 {act}")
    return 0


def cmd_review(args) -> int:
    project = Path(args.project_dir)
    if not project.is_dir():
        print(f"❌ 项目目录不存在：{project}", file=sys.stderr)
        return 2

    states = gates.load_states()
    cfg_gates = states.get("gates", {})
    if not cfg_gates:
        print("⚠️ gate_states.yaml 无闸口登记")
        return 0

    changed = False
    for name, cfg in cfg_gates.items():
        if cfg.get("status") == "strict":
            continue  # 已是硬闸，不再调整

        rows = gates.read_observations(project, name)
        fresh = [r for r in rows if not r.get("counted")]
        if not fresh:
            continue  # 本项目没跑过该闸，或已计入过，不计观察

        fp_rows = [r for r in fresh if r.get("false_positive")]
        cfg.setdefault("observed_projects", 0)
        cfg.setdefault("false_positives", 0)

        if fp_rows:
            cfg["false_positives"] += len(fp_rows)
            cfg["observed_projects"] = 0
            action = "⚠️ 发现误报，观察计数清零，保持观察期"
        else:
            cfg["observed_projects"] += 1
            thr = int(cfg.get("threshold_projects", 1))
            if cfg["observed_projects"] >= thr:
                cfg["status"] = "strict"
                cfg["activated_at"] = gates.today_str()
                cfg["activated_project"] = project.name
                action = "✅ 连续无误报达标，自动转阻塞硬闸"
            else:
                action = f"观察计数 {cfg['observed_projects']}/{thr}，继续观察期"

        gates.mark_counted(project, name, {r["ts"] for r in fresh})
        changed = True
        print(f"[{cfg.get('display', name)}] {action}")

    if changed:
        gates.save_states(states)
        print("已写回 workflow/gate_states.yaml")
    else:
        print("无需要计入的观察记录（闸口已硬闸，或本项目未跑过新闸）")
    return 0


def cmd_mark_fp(args) -> int:
    project = Path(args.project_dir)
    if not project.is_dir():
        print(f"❌ 项目目录不存在：{project}", file=sys.stderr)
        return 2
    ok = gates.mark_fp(project, args.gate, args.note or "")
    if not ok:
        print(f"❌ {args.gate} 未找到可标记的观察记录", file=sys.stderr)
        return 2
    print(f"✅ 已把 {args.gate} 最近一条观察记录标为误报；下次 review 计入清零")
    return 0


def main():
    ap = argparse.ArgumentParser(description="新闸观察期管理器（自动转硬闸）")
    sub = ap.add_subparsers(dest="command", required=True)

    p_status = sub.add_parser("status", help="查看各闸观察/硬闸状态")
    p_status.set_defaults(func=cmd_status)

    p_review = sub.add_parser("review", help="按项目观察日志判定是否自动转硬闸")
    p_review.add_argument("project_dir")
    p_review.set_defaults(func=cmd_review)

    p_fp = sub.add_parser("mark-fp", help="把最近一条观察记录标为误报")
    p_fp.add_argument("project_dir")
    p_fp.add_argument("--gate", required=True, choices=["input_card", "criterion_mapping"])
    p_fp.add_argument("--note", default="")
    p_fp.set_defaults(func=cmd_mark_fp)

    args = ap.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    _force_utf8_output()
    main()
