#!/usr/bin/env python3
"""
设计 → 实施 100% 映射核对（改进建议 #52④ / 用户 2026-10-30 硬要求）

专治「设计书/架构里写了，实际开发时忽略或省略，直到冒烟才发现功能压根没写」。

项目根目录 `_设计实施映射表.md` 是唯一核对载体（第 4 步建表，5A/5B/6/7/8/9 逐行更新）：
    | 编号 | 设计来源 | 设计项（功能/链路） | 端到端链路（输入→处理→输出） | 用户操作路径 | 实现落点 | 状态 | 验证证据 |

状态只允许四种：
    ❌未实现         → 第 6 步起阻塞（stage 6/9/10）
    ⚠️已实现未验证   → 第 9/10 步阻塞（stage 9/10）
    ✅已实现已验证   → 通过；但 stage 10 交付阶段「验证证据」列不得为空/—/无/待补/TODO
    ✂️明确砍掉       → 必须在「验证证据」列写「砍掉依据：…」，否则阻塞

条数下限：`min_rows`（默认 0，由 workflow_completion_check.py 从 steps.yaml 的
mapping.min_rows 传入）；映射表数据行数低于该阈值即报 MAPPING_NOT_READY。

使用方法：
    python scripts/design_impl_check.py <项目目录> --stage 4    # 建表结构检查，允许未实现
    python scripts/design_impl_check.py <项目目录> --stage 6    # 冒烟前：不允许 ❌未实现
    python scripts/design_impl_check.py <项目目录> --stage 10   # 交付门禁：❌/⚠️/✅缺证据 一律不允许
    python scripts/design_impl_check.py <项目目录> --stage 10 --min-rows 10   # 额外卡条数下限
    python scripts/design_impl_check.py <项目目录> --stage 10 --json

退出码：0 = 通过；1 = 有 ❌/⚠️/缺证据/结构/条数问题；2 = 参数或文件读取错误。
"""

import argparse
import json
import sys
from pathlib import Path

DEFAULT_MAPPING_PATH = "_设计实施映射表.md"

REQUIRED_COLUMNS = [
    "编号", "设计来源", "设计项", "端到端链路",
    "用户操作路径", "实现落点", "状态", "验证证据",
]

STATUS_VERIFIED = "verified"
STATUS_UNVERIFIED = "unverified"
STATUS_MISSING = "missing"
STATUS_CUT = "cut"
STATUS_UNKNOWN = "unknown"
STATUS_EVIDENCE = "MAPPING_EVIDENCE"  # stage 10：✅ 行缺「验证证据」

# 「验证证据」占位值（交付阶段一律视为没写证据）
EVIDENCE_PLACEHOLDERS = {"", "无", "待补", "待补充", "待验证", "todo", "tbd", "n/a", "na", "..."}


def _evidence_is_empty(value: str) -> bool:
    """判断「验证证据」是否为空/占位（空、—、-、无、待补、TODO 等）。"""
    v = (value or "").strip().strip("*").strip()
    if not v:
        return True
    compact = v.lower().replace("—", "").replace("－", "").replace("-", "").replace(" ", "").strip()
    if not compact:
        return True
    return compact in EVIDENCE_PLACEHOLDERS


def _cell(value: str) -> str:
    return value.strip().strip("*").strip()


def _classify(status_raw: str) -> str:
    """把状态单元格映射到四类之一；无法识别返回 unknown。"""
    s = status_raw.replace(" ", "")
    if "✂" in s or "砍掉" in s:
        return STATUS_CUT
    if "❌" in s or "未实现" in s:
        return STATUS_MISSING
    if "✅" in s or "已实现已验证" in s:
        return STATUS_VERIFIED
    if "⚠" in s or "未验证" in s or "已实现未验证" in s:
        return STATUS_UNVERIFIED
    return STATUS_UNKNOWN


def _find_header(lines: list[str]) -> tuple[int, dict] | tuple[None, None]:
    for i, line in enumerate(lines):
        if not line.strip().startswith("|"):
            continue
        cells = [_cell(c) for c in line.strip().strip("|").split("|")]
        joined = " ".join(cells)
        if "状态" in joined and ("设计项" in joined or "编号" in joined):
            idx = {}
            for col in REQUIRED_COLUMNS:
                for j, c in enumerate(cells):
                    if col in c:
                        idx[col] = j
                        break
            return i, idx
    return None, None


def check_project(project_dir: str | Path, stage: str = "10",
                  mapping_path: str = DEFAULT_MAPPING_PATH,
                  min_rows: int = 0) -> dict:
    """核心核对，返回结构化结果，供 CLI 与 workflow_completion_check.py 共用。

    min_rows：映射表数据行数下限（0 = 不限制，由 steps.yaml 的 mapping.min_rows 决定）。
    """
    root = Path(project_dir).resolve()
    path = root / mapping_path
    stage = str(stage)
    delivery = stage in ("10", "10.0")
    result = {
        "path": mapping_path,
        "stage": stage,
        "status": "OK",
        "details": "",
        "total": 0,
        "verified": 0,
        "unverified": 0,
        "missing": 0,
        "cut": 0,
        "min_rows": min_rows,
        "evidence_missing": 0,
        "evidence_missing_rows": [],
        "invalid_rows": [],
        "mapping_path": str(path),
    }

    if not path.exists():
        result["status"] = "MAPPING_MISSING"
        result["details"] = "缺少 _设计实施映射表.md（第 4 步必须建表）"
        return result

    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    header_i, idx = _find_header(lines)
    if header_i is None or idx is None:
        result["status"] = "MAPPING_STRUCTURE"
        result["details"] = "找不到表头（需含 编号/设计来源/设计项/状态/验证证据 等列）"
        return result

    lacking = [c for c in REQUIRED_COLUMNS if c not in idx]
    if lacking:
        result["status"] = "MAPPING_STRUCTURE"
        result["details"] = f"表头缺少列：{', '.join(lacking)}"
        return result

    rows = []
    for line in lines[header_i + 1:]:
        if not line.strip().startswith("|"):
            continue
        cells = [_cell(c) for c in line.strip().strip("|").split("|")]
        if all(set(c) <= set("-: ") for c in cells if c):
            continue  # 分隔行
        def get(col: str) -> str:
            j = idx[col]
            return cells[j] if j < len(cells) else ""
        row_id = get("编号")
        if not row_id:
            continue
        rows.append({
            "id": row_id,
            "source": get("设计来源"),
            "item": get("设计项"),
            "chain": get("端到端链路"),
            "path": get("用户操作路径"),
            "impl": get("实现落点"),
            "status_raw": get("状态"),
            "evidence": get("验证证据"),
            "row": " | ".join(cells),
        })

    result["total"] = len(rows)
    if not rows:
        result["status"] = "MAPPING_EMPTY"
        result["details"] = "表里没有任何数据行（设计书/架构条目一条都没抄）"
        return result

    seen_ids = {}
    problems = []
    for r in rows:
        cls = _classify(r["status_raw"])
        if cls == STATUS_VERIFIED:
            result["verified"] += 1
            # 交付阶段：✅ 行必须写实测证据，否则「已实现已验证」只是自填
            if delivery and _evidence_is_empty(r["evidence"]):
                result["evidence_missing"] += 1
                result["evidence_missing_rows"].append(r["id"])
        elif cls == STATUS_UNVERIFIED:
            result["unverified"] += 1
        elif cls == STATUS_MISSING:
            result["missing"] += 1
        elif cls == STATUS_CUT:
            result["cut"] += 1
            if "依据" not in (r["evidence"] + r["status_raw"]):
                result["invalid_rows"].append(f"{r['id']}：砍掉但未写「砍掉依据」")
        else:
            result["invalid_rows"].append(f"{r['id']}：状态无法识别（{r['status_raw'] or '空'}）")
            continue
        if r["id"] in seen_ids:
            result["invalid_rows"].append(f"{r['id']}：编号重复")
            continue
        seen_ids[r["id"]] = r

    if not result["invalid_rows"]:
        for r in rows:
            if r["item"] and not (r["source"] or r["impl"]):
                result["invalid_rows"].append(f"{r['id']}：缺「设计来源」或「实现落点」")
            elif not r["item"]:
                result["invalid_rows"].append(f"{r['id']}：缺「设计项」")

    if stage in ("9", "10", "10.0"):
        blockers = result["missing"] + result["unverified"]
    elif stage == "6":
        blockers = result["missing"]
    else:  # stage 4 只查结构
        blockers = 0

    too_few = min_rows > 0 and result["total"] < min_rows
    if result["invalid_rows"]:
        result["status"] = "MAPPING_STRUCTURE"
        result["details"] = "；".join(result["invalid_rows"][:8])
    elif too_few:
        result["status"] = "MAPPING_NOT_READY"
        result["details"] = (f"映射表仅 {result['total']} 行，低于 min_rows={min_rows}"
                             f"（设计书/架构要素疑似没抄全）")
        if blockers:
            result["details"] += f"；另有 ❌/⚠️ 阻塞 {blockers} 条"
        if result["evidence_missing"]:
            result["details"] += f"；{result['evidence_missing']} 条 ✅ 行缺验证证据"
    elif blockers:
        result["status"] = "MAPPING_NOT_READY"
        parts = []
        if result["missing"]:
            parts.append(f"❌未实现 {result['missing']} 条")
        if result["unverified"] and stage in ("9", "10", "10.0"):
            parts.append(f"⚠️已实现未验证 {result['unverified']} 条")
        if result["evidence_missing"]:
            parts.append(f"{result['evidence_missing']} 条 ✅ 行缺验证证据")
        result["details"] = "、".join(parts)
    elif result["evidence_missing"]:
        result["status"] = STATUS_EVIDENCE
        shown = "、".join(result["evidence_missing_rows"][:8])
        if len(result["evidence_missing_rows"]) > 8:
            shown += "…"
        result["details"] = (f"{result['evidence_missing']} 条 ✅ 行「验证证据」为空/占位"
                             f"（交付阶段必须写实测证据：{shown}）")
    return result


def main():
    ap = argparse.ArgumentParser(description="设计→实施 100% 映射核对")
    ap.add_argument("project_dir", help="项目目录，如 projects/xxx")
    ap.add_argument("--stage", default="10", choices=["4", "6", "9", "10", "10.0"],
                    help="核对阶段：4=只查结构；6=禁止 ❌未实现；9/10=❌ 与 ⚠️ 都不允许，"
                         "且 10 还要求 ✅ 行写验证证据")
    ap.add_argument("--path", default=DEFAULT_MAPPING_PATH, help="映射表相对路径")
    ap.add_argument("--min-rows", type=int, default=0,
                    help="映射表数据行数下限（0=不限制；门禁由 steps.yaml mapping.min_rows 传入）")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args()

    if not Path(args.project_dir).is_dir():
        print(f"❌ 项目目录不存在：{args.project_dir}", file=sys.stderr)
        sys.exit(2)

    r = check_project(args.project_dir, args.stage, args.path, min_rows=args.min_rows)
    if args.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        print(f"\n=== 设计→实施映射核对（stage {r['stage']}）：{Path(args.project_dir).name} ===")
        print(f"映射表：{r['path']}" + (f"（min_rows={r['min_rows']}）" if r["min_rows"] else ""))
        if r["status"] == "MAPPING_MISSING":
            print(f"❌ {r['details']}")
        elif r["status"] == "MAPPING_EMPTY":
            print(f"❌ {r['details']}")
        elif r["status"] == "MAPPING_STRUCTURE":
            print(f"❌ 表结构/行内容有问题：{r['details']}")
        else:
            print(f"条目 {r['total']}：✅ 已验证 {r['verified']} / ⚠️ 未验证 {r['unverified']} / "
                  f"❌ 未实现 {r['missing']} / ✂️ 砍掉 {r['cut']}"
                  + (f" / ✅缺证据 {r['evidence_missing']}" if r["evidence_missing"] else ""))
            if r["status"] == "MAPPING_NOT_READY":
                print(f"🔴 {r['details']}（stage {r['stage']} 不允许）")
            elif r["status"] == STATUS_EVIDENCE:
                print(f"🔴 {r['details']}")
                print("   补法：给每条 ✅ 行写实测证据（接口返回/截图路径/日志片段/测试名），"
                      "不能只填「已实现」或「—」。")
            else:
                print("✅ 通过：本阶段无阻塞项")
        print("口径：❌未实现 = 设计里有、代码里没有；⚠️已实现未验证 = 写了但没按用户操作路径跑通过；"
              "✂️砍掉 = 必须附「砍掉依据」并已写进设计书 §8/基线排除范围。")
    sys.exit(0 if r["status"] == "OK" else 1)


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
