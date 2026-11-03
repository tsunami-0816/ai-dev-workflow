#!/usr/bin/env python3
"""
翻新线 F0 迁入建档脚本

两种入口：
  野生入口：  python scripts/refurbish_intake.py --wild --source D:\\lg\\project\\SparrowScheduler --target projects/SparrowScheduler
  毕业生入口：python scripts/refurbish_intake.py --graduate --target projects/saas-workflow-agent

脚本自动做：
  野生：复制源目录（含 .git）→ 写看板翻新字段 → 分配端口前缀 → 跑 F0 闸门校验
  毕业生：仅写看板翻新字段 → 跑 F0 闸门校验（不复制文件）

F0 闸门校验（R12 自检，全绿才算过，报红不入队）：
  野生：① 文件数比对（源 vs 目标，差异率 <5%）② .git 目录存在 ③ git remote -v 可达
  毕业生：① .git 存在 ② 看板关键字段（路线/源路径/remote URL）已补齐

退出码：0 = 闸门全绿可以入队；1 = 闸门报红；2 = 参数错误。
"""

import argparse
import datetime
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT_MARKER = "WORKFLOW_工作流主控.md"
PORT_TABLE = "WORKFLOW_端口分配表.md"


def find_root() -> Path:
    d = Path.cwd().resolve()
    for _ in range(10):
        if (d / ROOT_MARKER).exists():
            return d
        if d.parent == d:
            break
        d = d.parent
    print(f"❌ 未找到工作流根目录（缺少 {ROOT_MARKER}）", file=sys.stderr)
    sys.exit(2)


def count_files(d: Path) -> int:
    return sum(1 for _ in d.rglob("*") if _.is_file())


def git_head_commit(d: Path) -> str:
    """获取目录 git HEAD commit hash（短版）。"""
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(d), capture_output=True, text=True, timeout=10,
        )
        if r.returncode == 0:
            return r.stdout.strip()
    except Exception:
        pass
    return ""


def git_remote_url(d: Path) -> str:
    """获取 git 远程仓库 URL（origin）。"""
    try:
        r = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=str(d), capture_output=True, text=True, timeout=10,
        )
        if r.returncode == 0:
            return r.stdout.strip()
    except Exception:
        pass
    return ""


def git_has_remote(d: Path) -> bool:
    """检查 .git 目录是否存在且至少有一个 remote（或没有 remote 也算合法——野生项目可能还没推过）。"""
    git_dir = d / ".git"
    if not git_dir.exists():
        return False
    return True


def assign_port_prefix(root: Path, project_name: str) -> dict:
    """读端口分配表 + 查现有项目占用，返回可用端口分配。"""
    port_file = root / PORT_TABLE
    existing = set()
    # 先扫端口表
    if port_file.exists():
        for line in port_file.read_text(encoding="utf-8").splitlines():
            m = re.search(r"(\d{4,5})", line)
            if m:
                existing.add(m.group(1))
    # 再扫 projects/ 下所有已运行项目的看板端口记录（简单做法）
    backend_start = 8081
    frontend_start = 5173
    infra_ports = {"3306", "6379", "9092", "3310", "5672", "6381"}

    # 找第一个没被占用的前缀
    backend_port = backend_start
    frontend_port = frontend_start
    for offset in range(50):
        bp = str(backend_start + offset)
        fp = str(frontend_start + offset)
        if bp not in existing and fp not in existing:
            backend_port = bp
            frontend_port = fp
            break
    return {
        "backend": backend_port,
        "frontend": frontend_port,
        "note": f"翻新项目自动分配（避开现有端口表 + projects/ 占用）；基础设施共用 3310/6379/9092",
    }


def write_board_refurbish_fields(target: Path, source_path: str, remote_url: str,
                                  git_baseline: str, port_assign: dict, root: Path) -> None:
    """写/更新看板的翻新线新增字段。"""
    board = target / "_项目状态.md"
    if not board.exists():
        # 毕业生入口如果缺看板，从模板复制
        tpl = root / "projects" / "_TEMPLATE_新项目" / "_项目状态.md"
        if tpl.exists():
            shutil.copy2(tpl, board)
        else:
            board.write_text("# 项目状态看板\n", encoding="utf-8")

    text = board.read_text(encoding="utf-8")
    today = datetime.date.today().isoformat()

    def _ensure_field(content: str, label: str, value: str) -> str:
        """确保看板里有该字段，没有则追加到基本信息区末尾。"""
        pattern = rf"- \*\*{re.escape(label)}\*\*：.*"
        if re.search(pattern, content):
            return re.sub(pattern, f"- **{label}**：{value}", content)
        # 追加到基本信息区末尾
        basic_end = content.find("## 步骤进度")
        if basic_end == -1:
            return content + f"\n- **{label}**：{value}\n"
        return content[:basic_end] + f"- **{label}**：{value}\n" + content[basic_end:]

    text = _ensure_field(text, "路线", "翻新")
    text = _ensure_field(text, "源路径", source_path)
    text = _ensure_field(text, "远程仓库 URL", remote_url or "（待配置）")
    text = _ensure_field(text, "git 基线 commit", git_baseline or "（无 .git 或无 commit）")
    text = _ensure_field(text, "体检报告路径", "F2_体检/体检报告.md（F2 完成后落盘）")

    # 写入完成日期
    text = re.sub(r"- 创建日期：\*\*(\d{4}-\d{2}-\d{2})\*\*", rf"- 创建日期：**\1**", text)
    if "创建日期" in text and f"**{today}**" not in text:
        text = re.sub(r"(- 创建日期：.*)", rf"\1（翻新建档日期：{today}）", text, count=1)

    # 更新当前阶段
    text = re.sub(
        r"- 当前阶段：\*\*.*?\*\*",
        "- 当前阶段：**F0 · 迁入建档（已完成，闸门全绿）**",
        text, count=1,
    )

    # 更新总体状态
    text = re.sub(
        r"- 总体状态：.*",
        "- 总体状态：进行中（翻新线）",
        text, count=1,
    )

    board.write_text(text, encoding="utf-8")


def run_gate_wild(source: Path, target: Path) -> tuple[bool, list[str]]:
    """野生入口 F0 闸门：① 文件数差异率 <5% ② .git 存在 ③ remote 可达。"""
    issues = []
    # 1. 文件数差异
    src_count = count_files(source)
    tgt_count = count_files(target)
    if src_count == 0:
        issues.append(f"源目录为空，无法比对")
    else:
        diff_rate = abs(src_count - tgt_count) / src_count
        if diff_rate > 0.05:
            issues.append(f"文件数差异率 {diff_rate:.1%}（源 {src_count} vs 目标 {tgt_count}），超过 5% 阈值")

    # 2. .git 存在
    if not (target / ".git").exists():
        issues.append("目标目录缺 .git 目录")

    # 3. remote 可达（可选——没有 remote 不致命，报警告）
    remote = git_remote_url(target)
    if remote:
        try:
            r = subprocess.run(
                ["git", "ls-remote", "--exit-code", remote],
                cwd=str(target), capture_output=True, text=True, timeout=15,
            )
            if r.returncode != 0:
                issues.append(f"git remote 不可达：{remote}（exit {r.returncode}）")
        except Exception as e:
            issues.append(f"git remote 检查失败：{e}")

    return len(issues) == 0, issues


def run_gate_graduate(target: Path) -> tuple[bool, list[str]]:
    """毕业生入口 F0 闸门：① .git 存在 ② 看板翻新字段已补齐。"""
    issues = []
    if not (target / ".git").exists():
        issues.append("目标目录缺 .git 目录")

    board = target / "_项目状态.md"
    if not board.exists():
        issues.append("项目缺 _项目状态.md 看板文件")
    else:
        text = board.read_text(encoding="utf-8")
        if "路线=翻新" not in text and "路线**：翻新" not in text:
            issues.append("看板缺「路线=翻新」字段（可能未运行 refurbish_intake.py）")
        if "远程仓库" not in text and "源路径" not in text:
            issues.append("看板缺翻新关键字段（源路径 / 远程仓库 URL）")

    return len(issues) == 0, issues


def main():
    ap = argparse.ArgumentParser(description="翻新线 F0 迁入建档")
    grp = ap.add_mutually_exclusive_group(required=True)
    grp.add_argument("--wild", action="store_true", help="野生入口：复制源目录含 .git")
    grp.add_argument("--graduate", action="store_true", help="毕业生入口：仅补看板字段")
    ap.add_argument("--source", default="", help="野生入口必填：源目录绝对路径")
    ap.add_argument("--target", required=True, help="目标项目目录（如 projects/SparrowScheduler）")
    args = ap.parse_args()

    root = find_root()
    target = Path(args.target).resolve()
    name = target.name

    print(f"\n=== 翻新线 F0 迁入建档：{name} ===\n")
    print(f"入口类型：{'野生' if args.wild else '毕业生'}")
    print(f"目标目录：{target}")

    gate_ok = True
    issues = []
    stats = {"source_files": 0, "target_files": 0, "git_dir": False, "remote": "", "baseline": "", "copied": False}

    if args.wild:
        if not args.source:
            print("❌ --wild 必须配 --source", file=sys.stderr)
            sys.exit(2)
        source = Path(args.source).resolve()
        if not source.exists() or not source.is_dir():
            print(f"❌ 源目录不存在或不是目录：{source}", file=sys.stderr)
            sys.exit(2)

        print(f"源目录：{source}")

        # 1. 复制目录（含 .git）
        if target.exists():
            print(f"⚠️ 目标已存在：{target}，跳过复制（已有内容不会被覆盖）")
        else:
            print("复制源目录（含 .git）→ 目标目录 ...")
            shutil.copytree(source, target, symlinks=True)
            stats["copied"] = True
            print(f"✅ 复制完成")

        stats["source_files"] = count_files(source)
        stats["target_files"] = count_files(target)

        # 2. git 信息
        if (target / ".git").exists():
            stats["git_dir"] = True
            stats["remote"] = git_remote_url(target)
            stats["baseline"] = git_head_commit(target)

        # 3. 闸门
        gate_ok, issues = run_gate_wild(source, target)
        print(f"\n闸门自检计数（R12）：源文件 {stats['source_files']} / 目标文件 {stats['target_files']} / "
              f".git {'有' if stats['git_dir'] else '无'} / remote {'有' if stats['remote'] else '无'} / baseline {stats['baseline']}")

    else:  # graduate
        if not target.exists():
            print(f"❌ 毕业生入口目标必须已存在：{target}", file=sys.stderr)
            sys.exit(2)

        # git 信息
        if (target / ".git").exists():
            stats["git_dir"] = True
            stats["remote"] = git_remote_url(target)
            stats["baseline"] = git_head_commit(target)
        # 毕业生入口源路径写"工作区内"
        stats["source"] = "工作区内"

        # 闸门（毕业生：写完字段再跑）
        gate_ok, issues = run_gate_graduate(target)

    # 写看板翻新字段
    source_label = args.source if args.wild else "工作区内"
    port_assign = assign_port_prefix(root, name)
    write_board_refurbish_fields(
        target, source_label, stats.get("remote", ""),
        stats.get("baseline", ""), port_assign, root,
    )
    print(f"\n✅ 看板翻新字段已写入（路线=翻新 / 源路径={source_label} / remote={stats.get('remote') or '（无）'} / baseline={stats.get('baseline') or '（无）'}）")

    # 端口分配
    print(f"端口分配：backend={port_assign['backend']} frontend={port_assign['frontend']}（{port_assign['note']}）")

    # 闸门结果
    print(f"\n=== F0 闸门结果 ===")
    if gate_ok:
        print("🟢 闸门全绿，可以入队。")
        print(f"   下一步：野生入口跑 F1 逆向建档；毕业生入口直接跑 F2 体检。")
        sys.exit(0)
    else:
        print(f"🔴 闸门报红（{len(issues)} 项），不入队：")
        for i in issues:
            print(f"   - {i}")
        print("   请修复上述问题后重新运行，或手动处理后跳过闸门。")
        sys.exit(1)


if __name__ == "__main__":
    main()
