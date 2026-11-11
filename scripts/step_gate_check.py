#!/usr/bin/env python3
"""
第 1 / 4 步机器闸门（2026-11-11 · 方案 P0-3）

为什么有它：卡点协议把第 1/4 步标成「🤖 机器闸门」，但此前只有 Agent 自检，
自检容易被 AI 自己判绿。本脚本把两步的核心检查固化成可回归的机器判据。

用法：
  python scripts/step_gate_check.py --step 1 --file 01_项目基线说明书.md
  python scripts/step_gate_check.py --step 4 --file 04_任务拆解与开发规范.md

第 1 步：量化指标表逐行「数字+单位 + 验证归属非空」；「排除范围」段非空。
第 4 步：「角色权限矩阵 / 异常分支 / 边界输入」三段齐全；异常分支覆盖
        网络失败|数据为空|重复提交|超时 中 ≥3 类；边界输入覆盖 超长|特殊字符|并发 中 ≥2 类。

退出码：0 通过；1 有未通过项；2 脚本自身错误（文件不存在/参数错）。
"""

import argparse
import re
import sys
from pathlib import Path

PLACEHOLDERS = {"", "-", "—", "无", "待补", "TODO", "todo", "TBD"}

UNIT_RE = re.compile(
    r"\d+(?:\.\d+)?\s*(?:ms|s|秒|分钟|小时|天|%|个|条|次|人|并发|QPS|qps|MB|GB|万|千)"
)

EXCEPTION_KEYWORDS = ["网络失败", "数据为空", "重复提交", "超时"]
BOUNDARY_KEYWORDS = ["超长", "特殊字符", "并发"]


def _force_utf8_output():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def _is_placeholder(text: str) -> bool:
    return text.strip().strip("：:") in PLACEHOLDERS


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _find_section(text: str, keyword: str) -> str:
    """取「包含 keyword 的标题/行」到下一个标题之间的正文；行内冒号后的内容也算。"""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if keyword not in line:
            continue
        # 行内内容：- **排除范围**：xxx / 排除范围：xxx
        inline = re.split(r"[：:]", line, maxsplit=1)
        body = [inline[1]] if len(inline) == 2 else []
        for follow in lines[i + 1:]:
            stripped = follow.strip()
            if stripped.startswith("#"):
                break
            body.append(follow)
        return "\n".join(body)
    return ""


def _section_has_content(body: str) -> bool:
    return any(not _is_placeholder(ln.strip().lstrip("-*`> ")) for ln in body.splitlines())


def check_step1(text: str) -> list[str]:
    errors: list[str] = []

    header_idx = None
    header = []
    for i, line in enumerate(text.splitlines()):
        if line.strip().startswith("|") and "指标" in line and (
            "目标" in line or "验证" in line
        ):
            header_idx = i
            header = _cells(line)
            break

    if header_idx is None:
        errors.append("缺少「量化指标」表（表头需同时含 指标 + 目标/验证）")
    else:
        metric_idx = next((i for i, h in enumerate(header) if "指标" in h), 0)
        verify_idx = next(
            (i for i, h in enumerate(header) if "验证" in h),
            len(header) - 1,
        )
        lines = text.splitlines()
        row_no = 0
        for line in lines[header_idx + 1:]:
            if not line.strip().startswith("|"):
                break
            cells = _cells(line)
            if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c) or not any(cells):
                continue
            row_no += 1
            name = cells[metric_idx] if metric_idx < len(cells) else f"第 {row_no} 行"
            row_text = " | ".join(cells)
            if not UNIT_RE.search(row_text):
                errors.append(f"第 {row_no} 行指标未量化（缺数字+单位）：{name}")
            verify = cells[verify_idx] if verify_idx < len(cells) else ""
            if _is_placeholder(verify):
                errors.append(f"第 {row_no} 行指标缺验证归属：{name}")

    excluded = _find_section(text, "排除范围")
    if not _section_has_content(excluded):
        errors.append("「排除范围」段缺失或为空，请补：不做的功能/不适用的场景")
    return errors


def check_step4(text: str) -> list[str]:
    errors: list[str] = []
    sections = {
        "角色权限矩阵": "按角色列出可访问的接口/数据与禁止操作",
        "异常分支": "失败/空数据/重复提交/超时等非正常路径",
        "边界输入": "超长/特殊字符/并发等极限输入",
    }
    for name, advice in sections.items():
        body = _find_section(text, name)
        if not _section_has_content(body):
            errors.append(f"缺少「{name}」段，建议补：{advice}")
            continue
        if name == "异常分支":
            hit = [k for k in EXCEPTION_KEYWORDS if k in body]
            if len(hit) < 3:
                miss = [k for k in EXCEPTION_KEYWORDS if k not in hit]
                errors.append(
                    f"「异常分支」仅覆盖 {len(hit)}/4 类，至少需 3 类；缺：{'、'.join(miss)}"
                )
        if name == "边界输入":
            hit = [k for k in BOUNDARY_KEYWORDS if k in body]
            if len(hit) < 2:
                miss = [k for k in BOUNDARY_KEYWORDS if k not in hit]
                errors.append(
                    f"「边界输入」仅覆盖 {len(hit)}/3 类，至少需 2 类；缺：{'、'.join(miss)}"
                )
    return errors


def main() -> int:
    ap = argparse.ArgumentParser(description="第 1 / 4 步机器闸门")
    ap.add_argument("--step", required=True, choices=["1", "4"], help="步骤号")
    ap.add_argument("--file", required=True, help="待校验的产物文件")
    args = ap.parse_args()

    path = Path(args.file)
    if not path.is_file():
        print(f"❌ 文件不存在：{path}", file=sys.stderr)
        return 2

    text = path.read_text(encoding="utf-8", errors="ignore")
    errors = check_step1(text) if args.step == "1" else check_step4(text)

    if errors:
        print(f"❌ 第 {args.step} 步闸门未通过（{path}）：")
        for e in errors:
            print(f"  - {e}")
        print("修法：按提示补齐后重跑本脚本；脚本不绿不得进入下一步。")
        return 1

    print(f"✅ 第 {args.step} 步闸门通过：{path}")
    return 0


if __name__ == "__main__":
    _force_utf8_output()
    sys.exit(main())
