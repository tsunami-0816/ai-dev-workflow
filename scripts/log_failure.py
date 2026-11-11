#!/usr/bin/env python3
"""
失败日志记录工具
每次返工/卡点发现问题时运行，把数据追加到项目根目录的 _失败日志.md
第 10 步复盘时直接读取这份日志做归因分析。

用法：
  python scripts/log_failure.py <项目目录> --step 6 --category "真实运行报错" --desc "npm install 报 ERESOLVE 依赖冲突" --ai-error "AI 编写的 package.json 中 react 版本与 antd 不兼容" --impact-file "frontend/package.json" --repro "npm install" --human-catch "" --rounds 2 --root-cause "幻觉依赖版本" --rule R8

可选 --rule：标注这次是哪条工作流规则兜住了这个坑（R<编号>），留空写「—」。

必填项说明：--step / --category / --desc / --impact-file / --repro 缺失或步骤名不在白名单内直接拒写，
避免出现「第第7步步」这类笔误与「没留复现命令」这类不可复盘记录。
"""

import argparse
import datetime
import re
import sys
from pathlib import Path

TEMPLATE_HEADER = """# 失败与返工日志

> 每次返工、卡点拦截、AI 犯错时由 `scripts/log_failure.py` 自动追加。
> 第 10 步复盘时直接基于本表做归因分析，替代「凭记忆写复盘」。
> 2026-10-28 起新增「影响文件」「复现命令」两列（旧记录无此两列，属正常）。
> 2026-10-29 起新增「触发规则」列：记录这次是哪条工作流规则兜住了这个坑（如 R13 数据重置），
> 供 WORKFLOW_规则库.md §8.0 规则登记表补源与 step11 体检统计。可留空，不额外增加流程步骤。

| 时间 | 步骤 | 失败类别 | 问题描述 | AI 所犯错误 | 人工卡点发现的 AI 遗漏 | 修复轮次 | 根因分类 | 影响文件 | 复现命令 | 触发规则 |
|---|---|---|---|---|---|---|---|---|---|---|
"""

VALID_STEPS = {"0", "1", "2", "3", "4", "5A", "5B", "5.5", "6", "6.5", "7", "7.5",
               "8", "8.5", "9", "10", "10.0", "10.5", "10.6", "11"}

CATEGORIES = [
    "AI产出错误",      # AI 生成的文档/代码本身有错
    "真实运行报错",    # 第 6 步起本地真实跑出来的报错
    "回归未通过",      # 修复后回归验证未通过
    "人工卡点拦截",    # 人工检查点发现的 AI 遗漏
    "评审打回",        # 第 3 步评审不通过
    "验收不通过",      # 第 9 步人工验收不通过
]

ROOT_CAUSES = [
    "幻觉依赖/版本",   # AI 编造不存在的包或版本号
    "跨文件不一致",    # 前后端接口、字段名对不上
    "沉默的缺失",      # AI 没写某功能且没主动说明
    "逻辑错误",        # 代码逻辑本身有 bug
    "需求理解偏差",    # AI 理解的需求与真实意图不符
    "上下文遗忘",      # 上下文太长导致前面约定被忘
    "安全问题",        # 硬编码密钥、注入、越权等
    "环境/配置",       # 本地环境、配置文件问题
    "其他",
]

HUMAN_CATCH_REQUIRED = ("人工卡点拦截", "验收不通过")


def _cell(value: str) -> str:
    """表格单元格转义：竖线替换为全角，换行压成空格"""
    return (value or "").replace("|", "｜").replace("\n", " ").strip()


def validate_step(step: str) -> str:
    """步骤名白名单校验（只接受纯编号，防「第第7步步」笔误）"""
    clean = (step or "").strip().upper()
    if not clean or "第" in clean or "步" in clean:
        raise ValueError(f"--step 必须是纯编号（如 6 / 8.5 / 5A），收到: {step!r}")
    if clean not in VALID_STEPS:
        raise ValueError(f"--step 非法: {step!r}；允许值: {', '.join(sorted(VALID_STEPS))}")
    return clean


def main():
    ap = argparse.ArgumentParser(description="记录一次失败/返工到 _失败日志.md")
    ap.add_argument("project_dir", help="项目目录（如 projects/xxx）")
    ap.add_argument("--step", required=True, help="发生失败的步骤编号，如 3 / 6 / 8 / 8.5")
    ap.add_argument("--category", required=True, choices=CATEGORIES)
    ap.add_argument("--desc", required=True, help="问题描述（一句话）")
    ap.add_argument("--ai-error", default="", help="AI 具体犯了什么错（没有则留空）")
    ap.add_argument("--human-catch", default="", help="人工卡点发现的 AI 遗漏（人工卡点拦截类必填）")
    ap.add_argument("--rounds", default="1", help="该问题修复用了几轮")
    ap.add_argument("--root-cause", default="其他", choices=ROOT_CAUSES)
    ap.add_argument("--impact-file", required=True, help="影响文件（多个用逗号分隔，必填）")
    ap.add_argument("--repro", required=True, help="复现命令/操作（必填，便于第 10 步复盘）")
    ap.add_argument("--rule", default="", help="本次是哪条工作流规则兜住/失效（如 R13），可留空")
    args = ap.parse_args()

    try:
        step = validate_step(args.step)
    except ValueError as e:
        print(f"❌ {e}")
        sys.exit(2)

    if not (args.impact_file or "").strip():
        print("❌ --impact-file 不能为空")
        sys.exit(2)
    if not (args.repro or "").strip():
        print("❌ --repro 不能为空（没有复现步骤的记录不可复盘）")
        sys.exit(2)
    if args.category in HUMAN_CATCH_REQUIRED and not (args.human_catch or "").strip():
        print(f"❌ 类别「{args.category}」必须填写 --human-catch（人工卡点具体发现了什么遗漏）")
        sys.exit(2)
    try:
        rounds = int(str(args.rounds).strip())
        if rounds < 0:
            raise ValueError
    except ValueError:
        print(f"❌ --rounds 必须是非负整数，收到: {args.rounds!r}")
        sys.exit(2)

    rule = (args.rule or "").strip().upper()
    if rule and not re.fullmatch(r"R\d+", rule):
        print(f"❌ --rule 必须写成 R<编号>（如 R13），收到: {args.rule!r}")
        sys.exit(2)

    log_path = Path(args.project_dir) / "_失败日志.md"
    if not log_path.exists():
        log_path.write_text(TEMPLATE_HEADER, encoding="utf-8")

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    row = (f"| {now} | 第{step}步 | {_cell(args.category)} | {_cell(args.desc)} | "
           f"{_cell(args.ai_error)} | {_cell(args.human_catch)} | {rounds} | "
           f"{_cell(args.root_cause)} | {_cell(args.impact_file)} | {_cell(args.repro)} | {rule or '—'} |\n")

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(row)

    print(f"✅ 已记录到 {log_path}")
    print(f"   [{args.category}] 第{step}步：{args.desc}")

    # 顺带输出当前统计
    lines = log_path.read_text(encoding="utf-8").splitlines()
    data_rows = [l for l in lines if l.startswith("| 2")]
    print(f"\n本项目已累计 {len(data_rows)} 条失败记录")
    by_step = {}
    for r in data_rows:
        cells = [c.strip() for c in r.split("|")]
        if len(cells) > 2:
            by_step[cells[2]] = by_step.get(cells[2], 0) + 1
    if by_step:
        top = sorted(by_step.items(), key=lambda x: -x[1])[:3]
        print("返工最多的步骤 Top3:", ", ".join(f"{s}({n}次)" for s, n in top))


def _force_utf8_output():
    """Windows 默认 cp936/GBK 控制台下打印中文/emoji 会 UnicodeEncodeError；入口处统一切 UTF-8。"""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


if __name__ == "__main__":
    _force_utf8_output()
    main()
