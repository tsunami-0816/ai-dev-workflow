#!/usr/bin/env python3
"""
前端 taste 审美检测：包装 tasteskill inspect.mjs，在真实浏览器里测页面是否"一眼 AI 模板味"。
和 design_quality_check.py（impeccable 扫硬伤）互补：
  - impeccable：扫对比度/padding/小字等可量化硬伤
  - taste inspect：扫"平均值页面"——居中大标题+三图标卡+柔渐变+等宽卡片这种整体气质

使用方法：
    python scripts/design_taste_gate.py --url http://localhost:5173              # C端/落地页
    python scripts/design_taste_gate.py --url http://localhost:5173 --app        # B端后台（app 模式）
    python scripts/design_taste_gate.py --url http://localhost:5173 --json out.json

第一期策略（R25，2026-11-05）：
    - 只产报告不阻塞。inspect.mjs 退出码 1（有 FAIL）时本脚本仍退出 0，
      把问题写进报告让人工/AI 决定改不改。
    - 跑 1-2 个项目观察误报率后，再决定是否改成硬卡（退出码 1）。
    - 已知坑：768px 宽度下 Edge 垂直滚动条占 ~15px，media query 断点要留 buffer。
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path


def run_inspect(url: str, as_app: bool, out_dir: str) -> tuple[int, str, str]:
    """调 node inspect.mjs，返回 (returncode, stdout, stderr)"""
    # taste-skill 仓库在工作流仓库 skills/active/taste-skill/
    repo_root = Path(__file__).resolve().parent.parent
    inspect_js = repo_root / "skills" / "active" / "taste-skill" / "scripts" / "inspect.mjs"

    if not inspect_js.exists():
        print(f"❌ 找不到 inspect.mjs: {inspect_js}")
        return 2, "", "missing inspect.mjs"

    cmd = ["node", str(inspect_js), url, "--out", out_dir, "--json"]
    if as_app:
        cmd.append("--app")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=180,
            encoding="utf-8",
            errors="replace",
        )
        return result.returncode, result.stdout, result.stderr
    except FileNotFoundError:
        print("❌ 未找到 node，请先安装 Node.js 22+")
        return 2, "", "node not found"
    except subprocess.TimeoutExpired:
        print("❌ taste inspect 超时（180s）")
        return 2, "", "timeout"


def parse_json_output(stdout: str) -> dict | None:
    """inspect.mjs --json 输出 JSON，找到第一个 { 开始解析"""
    if not stdout:
        return None
    # 前面可能有非 JSON 日志行
    for i, ch in enumerate(stdout):
        if ch == "{":
            try:
                return json.loads(stdout[i:])
            except json.JSONDecodeError:
                return None
    return None


def print_report(data: dict | None, returncode: int):
    print("\n" + "=" * 60)
    print("前端 taste 审美检测报告")
    print("=" * 60)
    if returncode == 0:
        print("\n✅ inspect.mjs 判定：无 FAIL 级问题")
    elif returncode == 1:
        print("\n⚠️ inspect.mjs 判定：有 FAIL 级问题（第一期只记录不阻塞）")
    else:
        print(f"\n❌ inspect.mjs 运行失败（exit={returncode}）")

    if data:
        # inspect 的 JSON 结构不确定，通用打印
        findings = data.get("fail") or data.get("findings") or data.get("violations") or []
        if findings:
            print(f"\nFAIL 项 {len(findings)} 条：")
            for f in findings[:20]:
                if isinstance(f, dict):
                    rule = f.get("rule", f.get("name", "?"))
                    why = f.get("why", f.get("reason", f.get("message", "")))
                    print(f"  - [{rule}] {str(why)[:120]}")
                else:
                    print(f"  - {str(f)[:120]}")
    print("=" * 60 + "\n")


def main():
    ap = argparse.ArgumentParser(description="前端 taste 审美检测（包装 inspect.mjs）")
    ap.add_argument("--url", required=True, help="运行中的前端页面地址，如 http://localhost:5173")
    ap.add_argument("--app", action="store_true", help="B端后台模式（按 dashboard/admin 规则判）")
    ap.add_argument("--out", default=".taste-skill/inspect", help="截图和报告输出目录")
    ap.add_argument("--json", help="把 JSON 结果写到指定文件")
    ap.add_argument("--project", help="项目名（用于自动记入 WORKFLOW_taste_gate_观察.md）")
    ap.add_argument("--project-type", default="", help="项目类型 b2b-admin/landing/portfolio/internal-tool")
    args = ap.parse_args()

    print(f"🔍 taste 检测：{args.url} {'(app模式)' if args.app else ''}")
    rc, stdout, stderr = run_inspect(args.url, args.app, args.out)

    if stderr and rc != 0:
        print(f"stderr: {stderr[:500]}")

    data = parse_json_output(stdout)
    print_report(data, rc)

    if args.json:
        out = Path(args.json)
        out.write_text(
            json.dumps({"returncode": rc, "data": data, "stderr": stderr[:500]}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"📄 JSON 写入：{out}")

    # 自动追加观察记录到工作流根目录的 WORKFLOW_taste_gate_观察.md
    if args.project:
        log_path = Path(__file__).resolve().parent.parent / "WORKFLOW_taste_gate_观察.md"
        fail_count = "?"
        if isinstance(data, dict):
            findings = data.get("fail") or data.get("findings") or data.get("violations") or []
            fail_count = len(findings) if isinstance(findings, list) else "?"
        import datetime
        now = datetime.datetime.now().strftime("%Y-%m-%d")
        row = f"| {now} | {args.project} | {args.project_type or '?'} | {args.url} | {rc} | {fail_count} | 未看 | |\n"
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(row)
        print(f"📝 已记入观察表：{log_path}")
        print(f"   人工标注：跑完报告后，请把上面这行的「未看」改成「真问题 N / 误报 M」")

    # 第一期：永远返回 0（只记录不阻塞）。观察 1-2 个项目后改成：
    #   sys.exit(1 if rc == 1 else 0)
    sys.exit(0)


if __name__ == "__main__":
    main()
