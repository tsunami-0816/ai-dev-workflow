#!/usr/bin/env python3
"""
wf — 从 0 到 1 项目自动工作流命令行工具

命令：
  wf init <项目名> [--desc "原始描述" | --desc-file 路径]   从模板创建新项目
  wf list                                                    列出所有项目
  wf status [项目名]                                          查看项目进度看板
  wf next [项目名]                                            当前步骤 + 应使用的提示词模板
  wf prompt <步骤号>                                          打印指定步骤的提示词模板（如 wf prompt 6 / wf prompt 8.5）
  wf advance <项目名> <阶段描述>                              更新看板「当前阶段」
  wf log <项目名> --step N --category ... --desc ...         记录失败日志
  wf check deps <路径>                                       依赖版本真实性校验
  wf check secrets <路径>                                    硬编码密钥扫描
  wf check contract export <url> <输出路径>                  导出后端 OpenAPI 契约
  wf check contract check <契约路径> <前端目录>               校验前端调用符合契约
  wf check regression <p0_cases.json>                        P0 自动化回归测试

工作流根目录识别：从当前目录向上查找含 WORKFLOW_工作流主控.md 的目录。
"""

import argparse
import datetime
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT_MARKER = "WORKFLOW_工作流主控.md"
TEMPLATE_NAME = "_TEMPLATE_新项目"


def find_root() -> Path:
    """从当前目录向上查找工作流根目录"""
    d = Path.cwd().resolve()
    for _ in range(10):
        if (d / ROOT_MARKER).exists():
            return d
        if d.parent == d:
            break
        d = d.parent
    print(f"❌ 未找到工作流根目录（缺少 {ROOT_MARKER}）。请在工作流目录内运行，或 cd 到该目录。")
    sys.exit(1)


def project_dir(root: Path, name: str) -> Path:
    p = root / "projects" / name
    if not p.exists():
        print(f"❌ 项目不存在：{p}")
        sys.exit(1)
    return p


def step_to_prompt(root: Path, step: str) -> Path:
    """步骤号 -> prompts/ 下的模板文件"""
    prompts = root / "prompts"
    if step in ("6.5",):
        print("第 6.5 步是脚本校验（api_contract_validator.py），无提示词模板。用 wf check contract ...")
        sys.exit(0)
    if step in ("8.5",):
        f = prompts / "step08_5_安全扫描.md"
        if f.exists():
            return f
    if step.upper() in ("5A", "5B"):
        f = prompts / f"step05{step.upper()}_后端开发.md" if step.upper() == "5A" else prompts / "step05B_前端开发.md"
        if f.exists():
            return f
    matches = sorted(prompts.glob(f"step{int(float(step)):02d}_*.md"))
    if matches:
        return matches[0]
    print(f"❌ 找不到第 {step} 步的提示词模板")
    sys.exit(1)


# ---------- 子命令 ----------

def cmd_init(args):
    root = find_root()
    tpl = root / "projects" / TEMPLATE_NAME
    dst = root / "projects" / args.name
    if dst.exists():
        print(f"❌ 项目已存在：{dst}")
        sys.exit(1)
    shutil.copytree(tpl, dst)

    desc = args.desc or ""
    if args.desc_file:
        desc = Path(args.desc_file).read_text(encoding="utf-8")
    if desc:
        (dst / "00_原始项目描述.md").write_text(f"# 原始项目描述 · {args.name}\n\n{desc}\n", encoding="utf-8")

    # 更新看板基本信息
    board = dst / "_项目状态.md"
    text = board.read_text(encoding="utf-8")
    text = text.replace("项目名：<项目名>", f"项目名：{args.name}")
    text = text.replace("创建日期：<YYYY-MM-DD>", f"创建日期：{datetime.date.today().isoformat()}")
    board.write_text(text, encoding="utf-8")

    print(f"✅ 项目已创建：{dst}")
    print(f"   下一步：把原始描述发给 AI，或直接运行 wf prompt 1 获取第 1 步提示词")


def cmd_list(_args):
    root = find_root()
    for p in sorted((root / "projects").iterdir()):
        if p.is_dir() and p.name != TEMPLATE_NAME:
            board = p / "_项目状态.md"
            stage = ""
            if board.exists():
                m = re.search(r"当前阶段：\*\*(.+?)\*\*", board.read_text(encoding="utf-8"))
                stage = m.group(1) if m else ""
            print(f"  📁 {p.name}  —  {stage}")


def cmd_status(args):
    root = find_root()
    board = project_dir(root, args.name) / "_项目状态.md"
    print(board.read_text(encoding="utf-8"))


def cmd_next(args):
    root = find_root()
    board = project_dir(root, args.name) / "_项目状态.md"
    text = board.read_text(encoding="utf-8")
    m = re.search(r"当前阶段：\*\*(.+?)\*\*", text)
    stage = m.group(1) if m else "未知"
    print(f"当前阶段：{stage}\n")

    m2 = re.search(r"第\s*([\d.]+[AB]?)\s*步", stage)
    if m2:
        step = m2.group(1)
        prompt = step_to_prompt(root, step)
        print(f"应使用的提示词模板：{prompt.relative_to(root)}")
        print("=" * 50)
        print(prompt.read_text(encoding="utf-8"))

    # 提示卡点
    block = re.search(r"## 当前卡点（需要用户做什么）\n\n(.*?)\n\n## ", text, re.DOTALL)
    if block and "无" not in block.group(1).strip()[:4]:
        print("=" * 50)
        print("⚠️ 当前卡点：")
        print(block.group(1).strip())


def cmd_prompt(args):
    root = find_root()
    prompt = step_to_prompt(root, args.step)
    print(prompt.read_text(encoding="utf-8"))


def cmd_advance(args):
    root = find_root()
    board = project_dir(root, args.name) / "_项目状态.md"
    text = board.read_text(encoding="utf-8")
    text = re.sub(r"- 当前阶段：\*\*.+?\*\*", f"- 当前阶段：**{args.stage}**", text)
    board.write_text(text, encoding="utf-8")
    print(f"✅ 看板已更新：当前阶段 = {args.stage}")


def cmd_log(args):
    root = find_root()
    script = root / "scripts" / "log_failure.py"
    cmd = [sys.executable, str(script), str(project_dir(root, args.name)),
           "--step", args.step, "--category", args.category,
           "--desc", args.desc, "--ai-error", args.ai_error or "",
           "--human-catch", args.human_catch or "",
           "--rounds", args.rounds, "--root-cause", args.root_cause]
    sys.exit(subprocess.call(cmd))


def cmd_check(args):
    root = find_root()
    scripts = root / "scripts"
    if args.kind == "deps":
        sys.exit(subprocess.call([sys.executable, str(scripts / "dependency_checker.py"), args.path]))
    elif args.kind == "secrets":
        sys.exit(subprocess.call([sys.executable, str(scripts / "security_scan_secrets.py"), args.path]))
    elif args.kind == "regression":
        sys.exit(subprocess.call([sys.executable, str(scripts / "p0_regression_test.py"), args.path]))
    elif args.kind == "contract":
        v = scripts / "api_contract_validator.py"
        if args.action == "export":
            sys.exit(subprocess.call([sys.executable, str(v), "export", args.a, args.b]))
        else:
            sys.exit(subprocess.call([sys.executable, str(v), "check", args.a, args.b]))


# ---------- 入口 ----------

def main():
    ap = argparse.ArgumentParser(prog="wf", description="从 0 到 1 项目自动工作流 CLI")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init", help="从模板创建新项目")
    p.add_argument("name")
    p.add_argument("--desc", default="")
    p.add_argument("--desc-file", default="")
    p.set_defaults(fn=cmd_init)

    p = sub.add_parser("list", help="列出所有项目")
    p.set_defaults(fn=cmd_list)

    p = sub.add_parser("status", help="查看项目进度看板")
    p.add_argument("name")
    p.set_defaults(fn=cmd_status)

    p = sub.add_parser("next", help="当前步骤 + 应使用的提示词模板")
    p.add_argument("name")
    p.set_defaults(fn=cmd_next)

    p = sub.add_parser("prompt", help="打印指定步骤的提示词模板")
    p.add_argument("step")
    p.set_defaults(fn=cmd_prompt)

    p = sub.add_parser("advance", help="更新看板当前阶段")
    p.add_argument("name")
    p.add_argument("stage")
    p.set_defaults(fn=cmd_advance)

    p = sub.add_parser("log", help="记录失败日志")
    p.add_argument("name")
    p.add_argument("--step", required=True)
    p.add_argument("--category", required=True,
                   choices=["AI产出错误", "真实运行报错", "回归未通过", "人工卡点拦截", "评审打回", "验收不通过"])
    p.add_argument("--desc", required=True)
    p.add_argument("--ai-error", default="")
    p.add_argument("--human-catch", default="")
    p.add_argument("--rounds", default="1")
    p.add_argument("--root-cause", default="其他",
                   choices=["幻觉依赖/版本", "跨文件不一致", "沉默的缺失", "逻辑错误", "需求理解偏差", "上下文遗忘", "安全问题", "环境/配置", "其他"])
    p.set_defaults(fn=cmd_log)

    p = sub.add_parser("check", help="机器校验（deps/secrets/contract/regression）")
    p.add_argument("kind", choices=["deps", "secrets", "contract", "regression"])
    p.add_argument("path", nargs="?", default=".")
    p.add_argument("action", nargs="?")
    p.add_argument("a", nargs="?")
    p.add_argument("b", nargs="?")
    p.set_defaults(fn=cmd_check)

    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
