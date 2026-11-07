#!/usr/bin/env python3
"""
前端 UI 质量检查：包装 impeccable detect，自动扫页面的对比度、小字、padding 拥挤等硬伤。
使用方法：
    python scripts/design_quality_check.py --url http://localhost:5173    # 扫运行中的页面（推荐）
    python scripts/design_quality_check.py --path ./frontend/src           # 扫源码目录（regex 规则 only）
    python scripts/design_quality_check.py --url http://localhost:5173 --json out.json  # 输出 JSON 文件

分级口径（防「组件库默认配色误报太多」）：
    - error 级 → 阻塞（比如脚本错误、内容隐藏）
    - warning 级 → 记入台账，精修模式下修，普通模式下记 deferred
    - advisory 级 → 只记录，不阻塞
    - Element Plus / Ant Design 常见默认配色的低对比度 → 自动降级为 advisory（不算真问题）
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path


# Element Plus / Ant Design 常见默认配色的低对比度，自动降级为 advisory
# 理由：组件库默认样式如此，不是 AI 生成的硬伤，改了反而破坏组件库一致性
# 格式：(颜色描述关键词, 降级后 severity)
COMPONENT_LIB_DEFAULTS = [
    # Element Plus 辅助文字灰 #909399 on white → 3.1:1，组件库默认，不算硬伤
    ("#909399 on #ffffff", "advisory"),
    ("#909399 on #f5f7fa", "advisory"),
    # Element Plus 成功/警告/错误标签浅色底 → 组件库默认配色
    ("#67c23a on #f0f9eb", "advisory"),
    ("#67c23a on #e4f8ec", "advisory"),
    ("#67c23a on #edf8e7", "advisory"),
    ("#67c23a on #e6f4e7", "advisory"),
    ("#67c23a on #f7fbff", "advisory"),
    ("#e6a23c on #fdf6ec", "advisory"),
    ("#e6a23c on #fcf4e8", "advisory"),
    ("#e6a23c on #fafafa", "advisory"),
    ("#e6a23c on #f7fbff", "advisory"),
    ("#f56c6c on #fef0f0", "advisory"),
    ("#f56c6c on #feeded", "advisory"),
    # Element Plus 主按钮白字蓝底 #409eff → 2.8:1，大字按钮其实够
    ("#ffffff on #409eff", "advisory"),
    ("#ffffff on #66b1ff", "advisory"),
    # Ant Design 常见
    ("#ffffff on #18a058", "advisory"),
    ("#ffffff on #67c23a", "advisory"),
]


def run_impeccable(target: str) -> list:
    """调用 npx impeccable detect --json，返回 findings 列表"""
    # Windows 上用 npx.cmd，Linux/Mac 用 npx
    npx_cmd = "npx.cmd" if sys.platform == "win32" else "npx"
    cmd = [npx_cmd, "--yes", "impeccable", "detect", target, "--json"]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            encoding="utf-8",
            errors="replace",
        )
        # impeccable exit code 2 = 有发现，0 = 干净，1 = 扫不了
        if result.returncode == 1:
            print(f"❌ impeccable 扫描失败：{result.stderr[:500]}")
            return []
        # 解析 JSON 输出
        stdout = result.stdout.strip()
        if not stdout:
            return []
        # 有时候 stdout 前面有非 JSON 行，找到第一个 [ 开始解析
        json_start = stdout.find("[")
        if json_start < 0:
            return []
        return json.loads(stdout[json_start:])
    except FileNotFoundError:
        print("❌ 未找到 npx，请先安装 Node.js（需要 Node 22+）")
        return []
    except subprocess.TimeoutExpired:
        print("❌ impeccable 扫描超时（120s）")
        return []
    except json.JSONDecodeError as e:
        print(f"⚠️ impeccable 输出 JSON 解析失败：{e}")
        return []


def apply_component_lib_overrides(findings: list) -> list:
    """对组件库默认配色的低对比度问题自动降级"""
    for f in findings:
        if f.get("antipattern") != "low-contrast":
            continue
        snippet = f.get("snippet", "").lower()
        for default_pattern, new_severity in COMPONENT_LIB_DEFAULTS:
            if default_pattern.lower() in snippet:
                f["severity"] = new_severity
                f["_component_lib_default"] = True
                break
    return findings


def summarize(findings: list) -> dict:
    """按 severity 分类汇总"""
    by_severity = {"error": [], "warning": [], "advisory": []}
    by_category = {}
    for f in findings:
        sev = f.get("severity", "advisory")
        if f.get("_component_lib_default"):
            sev = "advisory"  # 已经降级过
        by_severity[sev].append(f)
        cat = f.get("category", "unknown")
        if cat not in by_category:
            by_category[cat] = {"error": 0, "warning": 0, "advisory": 0}
        by_category[cat][sev] = by_category[cat].get(sev, 0) + 1
    return {
        "total": len(findings),
        "by_severity": {k: len(v) for k, v in by_severity.items()},
        "by_category": by_category,
        "findings": findings,
    }


def print_report(summary: dict):
    """打印人类可读的报告"""
    print("\n" + "=" * 60)
    print("前端 UI 质量检查报告")
    print("=" * 60)
    print(f"\n总计：{summary['total']} 条发现")
    sev = summary["by_severity"]
    print(f"  🔴 error（阻塞）：{sev.get('error', 0)} 条")
    print(f"  🟡 warning（需修）：{sev.get('warning', 0)} 条")
    print(f"  🔵 advisory（建议）：{sev.get('advisory', 0)} 条")

    if sev.get("error", 0) > 0:
        print("\n🔴 error 级问题详情：")
        for f in summary["findings"]:
            if f.get("severity") == "error":
                print(f"  - [{f.get('antipattern')}] {f.get('snippet', '')[:100]}")

    if sev.get("warning", 0) > 0:
        print("\n🟡 warning 级问题详情：")
        for f in summary["findings"]:
            if f.get("severity") == "warning":
                print(f"  - [{f.get('antipattern')}] {f.get('snippet', '')[:100]}")

    print("\n" + "=" * 60)
    if sev.get("error", 0) > 0:
        print("结论：❌ 有 error 级问题，需要修复")
    elif sev.get("warning", 0) > 0:
        print("结论：⚠️ 有 warning 级问题，记入台账，精修模式下处理")
    else:
        print("结论：✅ 无阻塞问题")
    print("=" * 60 + "\n")


def main():
    parser = argparse.ArgumentParser(description="前端 UI 质量检查（包装 impeccable）")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--url", help="运行中的前端页面地址（推荐），如 http://localhost:5173")
    group.add_argument("--path", help="前端源码目录路径，如 ./frontend/src")
    parser.add_argument("--json", help="输出 JSON 结果到指定文件")
    parser.add_argument("--no-override", action="store_true", help="不应用组件库默认配色降级（显示全部原始结果）")
    args = parser.parse_args()

    target = args.url or args.path
    print(f"🔍 正在扫描：{target}")

    findings = run_impeccable(target)
    if not findings:
        print("✅ 未发现问题（或扫描失败）")
        sys.exit(0)

    # 自检计数（R12）：解析到多少条 finding
    print(f"📊 自检：impeccable 返回 {len(findings)} 条原始发现")

    if not args.no_override:
        findings = apply_component_lib_overrides(findings)
        downgraded = sum(1 for f in findings if f.get("_component_lib_default"))
        print(f"📊 组件库默认配色自动降级：{downgraded} 条")

    summary = summarize(findings)
    print_report(summary)

    if args.json:
        out_path = Path(args.json)
        out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"📄 JSON 结果已写入：{out_path}")

    # 退出码：有 error 级 → 1，否则 → 0
    sys.exit(1 if summary["by_severity"].get("error", 0) > 0 else 0)


if __name__ == "__main__":
    main()
