#!/usr/bin/env python3
"""
断点标记 + 恢复决策树（G10 · 2026-11-11；方案 §3 G10）

中断后靠标记文件恢复，不靠猜看板；恢复不整段重跑；长脚本可重入。
断点目录：项目根 `.checkpoint/`（运行时状态，不进 10.0 门禁产物清单，.gitignore 已排除）。

用法：
  python scripts/checkpoint.py mark  <项目目录> --step 6 --command "npm run dev" --pid 12345 --output-path "06_冒烟/冒烟记录.md"
  python scripts/checkpoint.py done  <项目目录> --step 6 --exit-code 0
  python scripts/checkpoint.py status <项目目录> [--step 6]

`.checkpoint/<step>.json` 结构：
  {
    "step": "6",
    "command": "npm run dev",
    "pid": 12345,
    "started_at": "2026-11-11 14:30:00",
    "ended_at": null,
    "exit_code": null,
    "output_path": "06_冒烟/冒烟记录.md",
    "artifacts": ["06_冒烟/冒烟记录.md"]
  }

恢复决策树（status 命令按此给建议）：
  1. 产物已落盘 + exit_code=0      → 该步已完成，跳过
  2. pid 仍存活                    → 先探活，活着就等，不重启
  3. 进程死 + exit_code≠0          → 只重跑这一步
  4. 无标记文件                    → 从该步开始

硬规则：禁止整段从头重跑；恢复第一步永远先 `env_preflight.py --smoke <已知 URL>` 探活，服务活着不重启。
本期不做：自动崩溃重启、跨机器恢复、断点状态云端同步。

退出码：0 = 正常；2 = 脚本自身错误（参数/目录/IO）。
"""

import argparse
import datetime
import json
import os
import sys
from pathlib import Path

CHECKPOINT_DIR = ".checkpoint"


def _force_utf8_output():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def _now() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _pid_alive(pid: int | None) -> bool | None:
    """尽力探测进程是否存活；无法判定返回 None。"""
    if not pid:
        return None
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # 进程存在但无权访问
    except OSError:
        # Windows：os.kill 信号语义不同，退到 tasklist 探测
        try:
            import subprocess
            out = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}"],
                capture_output=True, text=True, timeout=5,
            )
            return str(pid) in out.stdout
        except Exception:
            return None


def _ckpt_path(root: Path, step: str) -> Path:
    return root / CHECKPOINT_DIR / f"{step}.json"


def cmd_mark(args) -> int:
    root = Path(args.project_dir)
    if not root.is_dir():
        print(f"❌ 项目目录不存在：{root}", file=sys.stderr)
        return 2
    ckpt = _ckpt_path(root, args.step)
    ckpt.parent.mkdir(parents=True, exist_ok=True)
    artifacts = [p for p in [args.output_path] if p]
    data = {
        "step": args.step,
        "command": args.command or "",
        "pid": args.pid,
        "started_at": _now(),
        "ended_at": None,
        "exit_code": None,
        "output_path": args.output_path or "",
        "artifacts": artifacts,
    }
    ckpt.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ 断点已标记：{ckpt.relative_to(root)}（step {args.step}）")
    return 0


def cmd_done(args) -> int:
    root = Path(args.project_dir)
    ckpt = _ckpt_path(root, args.step)
    if not ckpt.exists():
        print(f"❌ 该步无断点标记：{ckpt}", file=sys.stderr)
        return 2
    data = json.loads(ckpt.read_text(encoding="utf-8"))
    data["ended_at"] = _now()
    data["exit_code"] = args.exit_code
    ckpt.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ 断点已收口：step {args.step}，exit_code={args.exit_code}")
    return 0


def _latest_checkpoint(root: Path, step: str | None) -> Path | None:
    cdir = root / CHECKPOINT_DIR
    if not cdir.is_dir():
        return None
    files = sorted(cdir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if step:
        f = cdir / f"{step}.json"
        return f if f.exists() else None
    return files[0] if files else None


def cmd_status(args) -> int:
    root = Path(args.project_dir)
    if not root.is_dir():
        print(f"❌ 项目目录不存在：{root}", file=sys.stderr)
        return 2
    latest = _latest_checkpoint(root, args.step)
    if latest is None:
        print("=== 断点状态：无标记文件 ===")
        print("恢复建议：决策树分支 4 —— 从该步开始；禁止整段从头重跑。")
        print("硬规则：恢复先 `env_preflight.py --smoke <已知 URL>` 探活，服务活着不重启。")
        return 0

    data = json.loads(latest.read_text(encoding="utf-8"))
    print(f"=== 断点状态：step {data.get('step')}（{latest.name}）===")
    print(f"- 命令：{data.get('command') or '—'}")
    pid = data.get("pid")
    alive = _pid_alive(pid)
    alive_text = {True: "存活", False: "已退出", None: "未记录/无法判定"}[alive]
    print(f"- PID：{pid or '—'}（{alive_text}）")
    print(f"- 开始：{data.get('started_at')}  结束：{data.get('ended_at') or '—'}")
    artifacts = data.get("artifacts") or []
    for art in artifacts:
        exists = (root / art).exists()
        print(f"- 产物：{art}（{'存在' if exists else '缺失'}）")

    exit_code = data.get("exit_code")
    artifacts_ok = all((root / a).exists() for a in artifacts) if artifacts else True

    if artifacts_ok and exit_code == 0:
        branch = "分支 1 —— 产物已落盘且 exit_code=0，该步已完成，跳过。"
    elif alive is True:
        branch = "分支 2 —— 进程仍存活：先探活，活着就等，不重启。"
    elif alive is False and exit_code not in (0, None):
        branch = "分支 3 —— 进程已退出且 exit_code≠0：只重跑这一步，不整段重跑。"
    else:
        branch = "分支 3/4 —— 按进程与产物状态判定；缺标记信息则从该步开始。"

    print(f"\n恢复建议：{branch}")
    print("决策树：① 产物+exit0 → 跳过；② pid 存活 → 探活等待；③ 进程死+非0 → 只重跑本步；④ 无标记 → 从本步开始。")
    print("硬规则：禁止整段从头重跑；恢复先 `env_preflight.py --smoke <已知 URL>` 探活。")
    return 0


def main():
    ap = argparse.ArgumentParser(description="断点标记 + 恢复决策树（G10）")
    sub = ap.add_subparsers(dest="command", required=True)

    p_mark = sub.add_parser("mark", help="标记一个步骤断点")
    p_mark.add_argument("project_dir")
    p_mark.add_argument("--step", required=True)
    p_mark.add_argument("--command", default="")
    p_mark.add_argument("--pid", type=int, default=None)
    p_mark.add_argument("--output-path", default="")
    p_mark.set_defaults(func=cmd_mark)

    p_done = sub.add_parser("done", help="收口一个步骤断点")
    p_done.add_argument("project_dir")
    p_done.add_argument("--step", required=True)
    p_done.add_argument("--exit-code", type=int, default=0)
    p_done.set_defaults(func=cmd_done)

    p_status = sub.add_parser("status", help="读最新断点并给恢复建议")
    p_status.add_argument("project_dir")
    p_status.add_argument("--step", default=None)
    p_status.set_defaults(func=cmd_status)

    args = ap.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    _force_utf8_output()
    main()
