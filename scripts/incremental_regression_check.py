#!/usr/bin/env python3
"""
迭代线不退化核对脚本（I2 进 I3 前的机器闸门）。

职责（对应 WORKFLOW_步骤定义.md §3.5 / 卡点协议「迭代不退化校验闸」）：
  1. P0 探活：复用 p0_regression_test.py，跑本轮 p0_cases.json；沿用/演进用例不得失效。
     用例文件顺序：本轮次目录 `08_测试/<轮次>/p0_cases.json` → 回退 v1 根目录 `08_测试/p0_cases.json`；
     都无则 P0 段记跳过，不计失败。
  2. 指标不降对比：从增量基线书指标表读指标归属（沿用/演进/新增）与 v1 基线值，
     本轮实测值优先取本轮 `08_测试/<轮次>/基线指标验证表.md`，回退基线书「实测值」列。
     沿用/演进类本轮实测不得跌破 v1 基线；新增类只看本轮达标。
  3. 输出 `08_测试/<轮次>/不退化报告.md`；退出码 0=全绿（含跳过/待人工核对），1=有 P0 失败或指标跌破。

用法：
  python scripts/incremental_regression_check.py <项目目录>
  python scripts/incremental_regression_check.py .

首版口径说明（开放问题 2/3，二期细化）：
  - 指标表表头以增量基线书增量段为准：指标ID | 归属版本 | 类型 | 指标描述 | v1 基线值 | 本轮目标值 | 实测值 | 口径/来源
  - 数值只抽首个数字+单位；方向按指标描述关键词判定（耗时/延迟/内存/错误率=越低越好；成功率/通过率/吞吐=越高越好）；
    抽不出可比数值或方向不明的行记「无法自动比对，人工核对」，不计跌破。
"""

import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p0_regression_test as p0  # 复用 P0 用例执行与鉴权逻辑

LOWER_BETTER_KEYWORDS = ("耗时", "响应", "延迟", "p95", "p99", "内存", "cpu", "占用", "错误率", "失败率", "时长")
HIGHER_BETTER_KEYWORDS = ("成功率", "通过率", "可用性", "吞吐", "qps", "tps", "覆盖率", "正确率")
NEW_TYPES = ("新增", "new")
KEEP_TYPES = ("沿用", "keep", "演进", "evolve")


def _force_utf8_output():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""


def _read_round_tag(root: Path) -> str:
    board = root / "_项目状态.md"
    m = re.search(r"迭代轮次\*{0,2}[：:]\s*(v\d+)", _read_text(board))
    return m.group(1) if m else ""


def _resolve_round_dir(root: Path, round_tag: str) -> Path:
    """定位本轮次测试目录：看板轮次优先；否则 glob v* 取最新 mtime；再否则回退 08_测试 根目录。"""
    base = root / "08_测试"
    if round_tag:
        cand = base / round_tag
        if cand.is_dir():
            return cand
    round_dirs = [d for d in base.glob("v*") if d.is_dir()]
    if round_dirs:
        if round_tag:
            matched = [d for d in round_dirs if d.name == round_tag]
            if matched:
                return matched[0]
        return max(round_dirs, key=lambda d: d.stat().st_mtime)
    return base


def _find_case_file(round_dir: Path) -> Path | None:
    for cand in (round_dir / "p0_cases.json", round_dir.parent / "p0_cases.json"):
        if cand.exists():
            return cand
    return None


def run_p0_probe(round_dir: Path) -> dict:
    """P0 探活：复用 p0_regression_test 跑用例；无用例文件记跳过。"""
    case_file = _find_case_file(round_dir)
    result = {"status": "SKIPPED", "total": 0, "passed": 0, "failed": 0, "cases": [], "note": ""}
    if case_file is None:
        result["note"] = "未找到 p0_cases.json（本轮次目录与 v1 根目录均无），P0 探活跳过"
        return result

    raw = json.loads(case_file.read_text(encoding="utf-8"))
    if isinstance(raw, list):
        tokens, cases = {}, raw
    else:
        tokens, cases = {}, raw.get("cases", [])
        if raw.get("auth"):
            try:
                tokens = p0.obtain_tokens(raw["auth"])
            except Exception as e:
                result["status"] = "FAILED"
                result["note"] = f"登录阶段失败（环境问题，非产品 Bug）：{e}"
                return result

    if not cases:
        result["note"] = "p0_cases.json 用例列表为空，P0 探活跳过"
        return result

    case_results = [p0.run_case(c, tokens) for c in cases]
    result["cases"] = case_results
    result["total"] = len(case_results)
    result["passed"] = sum(1 for r in case_results if r["passed"])
    result["failed"] = result["total"] - result["passed"]
    result["status"] = "PASS" if result["failed"] == 0 else "FAILED"
    result["note"] = f"用例文件：{case_file.name}"
    return result


def _split_row(line: str) -> list[str]:
    cells = [c.strip() for c in line.split("|")[1:-1]]
    return cells


def _find_table_header(lines: list[str], keywords: tuple[str, ...]) -> int:
    for i, line in enumerate(lines):
        if line.strip().startswith("|") and all(k in line for k in keywords):
            return i
    return -1


def _extract_number(text: str) -> tuple[float | None, str]:
    """抽首个数字+单位；抽不到返回 (None, '')。"""
    if text is None:
        return None, ""
    m = re.search(r"(-?\d+(?:\.\d+)?)\s*(ms|s|%|次|个|条|人|笔|MB|KB|GB)?", str(text))
    if not m:
        return None, ""
    return float(m.group(1)), (m.group(2) or "")


def _direction(desc: str) -> str:
    low = any(k in desc.lower() for k in LOWER_BETTER_KEYWORDS)
    high = any(k in desc.lower() for k in HIGHER_BETTER_KEYWORDS)
    if low and not high:
        return "lower"
    if high and not low:
        return "higher"
    return "unknown"


def _parse_incremental_metrics(root: Path) -> list[dict]:
    """从基线说明书增量段指标表解析指标行。"""
    base_doc = root / "01_项目基线说明书.md"
    lines = _read_text(base_doc).splitlines()
    header_idx = _find_table_header(lines, ("类型", "v1 基线值"))
    if header_idx < 0:
        return []
    header = _split_row(lines[header_idx])

    def col(name: str) -> int:
        for i, h in enumerate(header):
            if name in h:
                return i
        return -1

    c_type = col("类型")
    c_base = col("v1 基线值")
    c_desc = col("指标描述")
    c_measure = col("实测值")
    c_id = col("指标ID")
    metrics = []
    for line in lines[header_idx + 2:]:
        if not line.strip().startswith("|"):
            break
        cells = _split_row(line)
        if len(cells) <= max(filter(lambda x: x >= 0, (c_type, c_base, c_desc, c_measure, c_id)), default=0):
            continue
        mtype = cells[c_type] if c_type >= 0 else ""
        if not mtype:
            continue
        metrics.append({
            "id": cells[c_id] if c_id >= 0 else "",
            "type": mtype,
            "desc": cells[c_desc] if c_desc >= 0 else "",
            "v1_baseline": cells[c_base] if c_base >= 0 else "",
            "actual": cells[c_measure] if c_measure >= 0 else "",
        })
    return metrics


def _override_actual_from_round(round_dir: Path, metrics: list[dict]) -> None:
    """本轮验证表按指标ID覆盖实测值（首版：表头含 指标ID/实测值 两列才解析）。"""
    verify = round_dir / "基线指标验证表.md"
    if not verify.exists():
        return
    lines = _read_text(verify).splitlines()
    header_idx = _find_table_header(lines, ("指标ID",))
    if header_idx < 0:
        return
    header = _split_row(lines[header_idx])
    c_id = next((i for i, h in enumerate(header) if "指标ID" in h), -1)
    c_actual = next((i for i, h in enumerate(header) if "实测" in h), -1)
    if c_id < 0 or c_actual < 0:
        return
    actual_map = {}
    for line in lines[header_idx + 2:]:
        if not line.strip().startswith("|"):
            break
        cells = _split_row(line)
        if len(cells) > max(c_id, c_actual):
            actual_map[cells[c_id]] = cells[c_actual]
    for m in metrics:
        if m["id"] in actual_map:
            m["actual"] = actual_map[m["id"]]


def compare_metrics(root: Path, round_dir: Path) -> dict:
    """指标不降对比。返回逐条判定 + 计数。"""
    metrics = _parse_incremental_metrics(root)
    _override_actual_from_round(round_dir, metrics)
    rows = []
    kept = breached = uncomparable = new_ok = new_missing = 0

    for m in metrics:
        mtype = m["type"].strip().lower()
        entry = {**m, "verdict": "", "note": ""}
        if mtype in NEW_TYPES:
            actual_num, _ = _extract_number(m["actual"])
            if actual_num is not None or (m["actual"] and m["actual"] not in ("—", "-", "待实测", "待补", "TODO")):
                entry["verdict"] = "新增达标"
                new_ok += 1
            else:
                entry["verdict"] = "新增待实测"
                new_missing += 1
            rows.append(entry)
            continue

        if mtype not in KEEP_TYPES:
            entry["verdict"] = "类型未识别"
            entry["note"] = "指标类型既非沿用/演进/新增，需人工核对"
            uncomparable += 1
            rows.append(entry)
            continue

        base_num, base_unit = _extract_number(m["v1_baseline"])
        actual_num, actual_unit = _extract_number(m["actual"])
        direction = _direction(m["desc"])
        if base_num is None or actual_num is None:
            entry["verdict"] = "无法自动比对"
            entry["note"] = "v1 基线值或本轮实测值抽不出数值，人工核对"
            uncomparable += 1
        elif base_unit != actual_unit:
            entry["verdict"] = "无法自动比对"
            entry["note"] = f"单位不一致（基线 {base_unit or '无'} / 实测 {actual_unit or '无'}），人工核对"
            uncomparable += 1
        elif direction == "unknown":
            entry["verdict"] = "无法自动比对"
            entry["note"] = "指标方向不明（高低好坏无法判定），人工核对"
            uncomparable += 1
        elif direction == "lower":
            if actual_num <= base_num:
                entry["verdict"] = "守住"
                kept += 1
            else:
                entry["verdict"] = "跌破"
                entry["note"] = f"越低越好：实测 {m['actual']} > v1 基线 {m['v1_baseline']}"
                breached += 1
        else:
            if actual_num >= base_num:
                entry["verdict"] = "守住"
                kept += 1
            else:
                entry["verdict"] = "跌破"
                entry["note"] = f"越高越好：实测 {m['actual']} < v1 基线 {m['v1_baseline']}"
                breached += 1
        rows.append(entry)

    return {
        "rows": rows,
        "total": len(rows),
        "kept": kept,
        "breached": breached,
        "uncomparable": uncomparable,
        "new_ok": new_ok,
        "new_missing": new_missing,
    }


def _read_prev_commit(root: Path) -> str:
    board = root / "_项目状态.md"
    m = re.search(r"上一轮 commit\*{0,2}[：:]\s*([0-9a-fA-F]{7,40})", _read_text(board))
    return m.group(1) if m else "—"


def write_report(root: Path, round_dir: Path, round_tag: str, p0_result: dict, metric_result: dict) -> Path:
    report_dir = round_dir
    report_dir.mkdir(parents=True, exist_ok=True)
    report = report_dir / "不退化报告.md"

    p0_bad = p0_result["status"] == "FAILED"
    metric_bad = metric_result["breached"] > 0
    overall = "全绿" if not (p0_bad or metric_bad) else "未通过"

    lines = [
        f"# 迭代不退化报告（{round_tag or '本轮次'}）",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 项目目录：`{root.name}`",
        f"- 迭代轮次：{round_tag or '（看板未填，按最新 v* 目录）'}",
        f"- 上一轮 commit：{_read_prev_commit(root)}",
        f"- **结论：{overall}**",
        "",
        "## 1. P0 探活（沿用/演进用例不得失效）",
        "",
    ]
    if p0_result["status"] == "SKIPPED":
        lines.append(f"- 跳过：{p0_result['note']}")
    else:
        lines.append(f"- 结果：{p0_result['passed']}/{p0_result['total']} 通过，{p0_result['failed']} 失败")
        lines.append(f"- 说明：{p0_result['note']}")
        lines.append("")
        lines.append("| 用例ID | 名称 | 结果 | 说明 |")
        lines.append("|---|---|---|---|")
        for c in p0_result["cases"]:
            mark = "通过" if c["passed"] else "失败"
            note = c.get("reason", "") or f"{c.get('elapsed_ms', '')}ms"
            lines.append(f"| {c['id']} | {c['name']} | {mark} | {note} |")

    lines += [
        "",
        "## 2. 指标不退化对比",
        "",
        f"- 指标总数：{metric_result['total']}；守住 {metric_result['kept']}；跌破 {metric_result['breached']}；"
        f"新增达标 {metric_result['new_ok']}；新增待实测 {metric_result['new_missing']}；无法自动比对（人工核对） {metric_result['uncomparable']}",
        "",
        "| 指标ID | 类型 | 指标描述 | v1 基线值 | 本轮实测 | 判定 | 说明 |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in metric_result["rows"]:
        lines.append(
            f"| {r['id']} | {r['type']} | {r['desc']} | {r['v1_baseline']} | {r['actual']} | {r['verdict']} | {r['note']} |"
        )

    lines += [
        "",
        "## 3. 结论与处置",
        "",
    ]
    if overall == "全绿":
        lines.append("- P0 探活通过（或跳过），沿用/演进指标未跌破 v1 基线；新增类已达标或待本轮补测。可进 I3。")
    else:
        lines.append("- 存在未守住项，回 I2 对应步骤修复并复跑本脚本；跌破 v1 基线的指标必须修复或显式记 deferred 并进诚实边界。")
    if metric_result["uncomparable"]:
        lines.append(f"- 另有 {metric_result['uncomparable']} 条指标无法自动比对，需人工核对后再收口。")

    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def _read_route(root: Path) -> str:
    board = root / "_项目状态.md"
    m = re.search(r"\*\*路线\*\*：\s*(生产|翻新|迭代)", _read_text(board))
    return m.group(1) if m else "生产"


def main(root_str: str) -> int:
    root = Path(root_str).resolve()
    if not root.exists():
        print(f"❌ 项目目录不存在：{root}")
        return 2

    if _read_route(root) != "迭代":
        print(f"⏭️  路线非迭代（{_read_route(root)}），不退化核对仅迭代线使用，跳过。")
        return 0

    round_tag = _read_round_tag(root)
    round_dir = _resolve_round_dir(root, round_tag)

    print(f"== 迭代不退化核对：{root.name}（轮次 {round_tag or '未标注'}） ==")
    p0_result = run_p0_probe(round_dir)
    metric_result = compare_metrics(root, round_dir)

    report = write_report(root, round_dir, round_tag, p0_result, metric_result)

    print(f"\nP0 探活：{p0_result['passed']}/{p0_result['total']} 通过"
          + ("（跳过）" if p0_result["status"] == "SKIPPED" else ""))
    print(f"指标：守住 {metric_result['kept']} / 跌破 {metric_result['breached']} / "
          f"新增达标 {metric_result['new_ok']} / 待实测 {metric_result['new_missing']} / "
          f"人工核对 {metric_result['uncomparable']}")
    print(f"报告：{report}")

    if p0_result["status"] == "FAILED" or metric_result["breached"] > 0:
        print("\n❌ 不退化核对未通过，禁止进 I3。")
        return 1
    print("\n✅ 不退化核对全绿（含跳过/待人工核对项，见报告）。")
    return 0


if __name__ == "__main__":
    _force_utf8_output()
    if len(sys.argv) < 2:
        print("用法: python scripts/incremental_regression_check.py <项目目录>")
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
