#!/usr/bin/env python3
"""
失败日志记录工具
每次返工/卡点发现问题时运行，把数据追加到项目根目录的 _失败日志.md
第 10 步复盘时直接读取这份日志做归因分析。

用法：
  python scripts/log_failure.py <项目目录> --step 6 --category "真实运行报错" --desc "npm install 报 ERESOLVE 依赖冲突" --ai-error "AI 编写的 package.json 中 react 版本与 antd 不兼容" --human-catch "" --rounds 2 --root-cause "幻觉依赖版本"
"""

import argparse
import datetime
from pathlib import Path

TEMPLATE_HEADER = """# 失败与返工日志

> 每次返工、卡点拦截、AI 犯错时由 `scripts/log_failure.py` 自动追加。
> 第 10 步复盘时直接基于本表做归因分析，替代「凭记忆写复盘」。

| 时间 | 步骤 | 失败类别 | 问题描述 | AI 所犯错误 | 人工卡点发现的 AI 遗漏 | 修复轮次 | 根因分类 |
|---|---|---|---|---|---|---|---|
"""

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


def main():
    ap = argparse.ArgumentParser(description="记录一次失败/返工到 _失败日志.md")
    ap.add_argument("project_dir", help="项目目录（如 projects/xxx）")
    ap.add_argument("--step", required=True, help="发生失败的步骤编号，如 3 / 6 / 8")
    ap.add_argument("--category", required=True, choices=CATEGORIES)
    ap.add_argument("--desc", required=True, help="问题描述（一句话）")
    ap.add_argument("--ai-error", default="", help="AI 具体犯了什么错（没有则留空）")
    ap.add_argument("--human-catch", default="", help="人工卡点发现的 AI 遗漏（没有则留空）")
    ap.add_argument("--rounds", default="1", help="该问题修复用了几轮")
    ap.add_argument("--root-cause", default="其他", choices=ROOT_CAUSES)
    args = ap.parse_args()

    log_path = Path(args.project_dir) / "_失败日志.md"
    if not log_path.exists():
        log_path.write_text(TEMPLATE_HEADER, encoding="utf-8")

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    row = f"| {now} | 第{args.step}步 | {args.category} | {args.desc} | {args.ai_error} | {args.human_catch} | {args.rounds} | {args.root_cause} |\n"

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(row)

    print(f"✅ 已记录到 {log_path}")
    print(f"   [{args.category}] 第{args.step}步：{args.desc}")

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


if __name__ == "__main__":
    main()
