#!/usr/bin/env python3
"""
工作流完成门禁检查（completion gate）
队列状态改为"已完成"前必须跑这个脚本。核对关键产物是否真实落盘且非空，并检查看板是否同步。
产物清单来自 workflow/steps.yaml（单一事实源），不在本脚本里另维护一份。
任何一项缺失 → 输出红色清单 + 建议回退到第一个缺失步骤，禁止改队列状态。

使用方法：
  python scripts/workflow_completion_check.py <项目目录>
  python scripts/workflow_completion_check.py projects/multi-tenant-crm-ticket --json

退出码：0 = 全绿可以交付；1 = 有缺失，必须回退补齐。
"""

import argparse
import json
import re
import sys
from pathlib import Path

STEPS_FILE = Path(__file__).resolve().parent.parent / "workflow" / "steps.yaml"
QUEUE_FILE = Path(__file__).resolve().parent.parent / "WORKFLOW_项目队列.md"
# 门禁上线日期：此日期前创建的项目，台账/10.6 为可选；之后的必查（方案 A，按创建日期切分）
GATE_LAUNCH_DATE = "2026-10-29"


def _parse_date(s: str) -> str:
    """从日期字符串里抽 YYYY-MM-DD。"""
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", s)
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else None


def _read_project_create_date(pdir: Path) -> str:
    """从项目看板的「创建日期」行取 YYYY-MM-DD。取不到返回 None。"""
    board = pdir / "_项目状态.md"
    if not board.exists():
        return None
    for line in board.read_text(encoding="utf-8", errors="ignore").splitlines():
        if "创建日期" in line:
            return _parse_date(line)
    return None


def _is_exempt(root: Path, project_name: str) -> tuple[bool, str]:
    """读 WORKFLOW_项目队列.md 的豁免清单，判断项目是否被豁免。"""
    if not QUEUE_FILE.exists():
        return False, ""
    text = QUEUE_FILE.read_text(encoding="utf-8", errors="ignore")
    block = re.search(r"## 已豁免项目.*?\| 项目名 \| 豁免原因.*?\n\|---.*?\n(.*?)(?=\n## |\Z)",
                      text, re.S)
    if not block:
        return False, ""
    for line in block.group(1).splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.split("|")[1:-1]]
        if not cells or cells[0] == "":
            continue
        if cells[0].strip() == project_name:
            reason = cells[1] if len(cells) > 1 else ""
            return True, reason
    return False, ""


def load_config() -> dict:
    """读取步骤单一清单全文。缺失或解析失败直接报错，不做静默兜底。"""
    try:
        import yaml
    except ImportError:
        print("❌ 缺少 PyYAML，请先 pip install pyyaml", file=sys.stderr)
        sys.exit(2)
    if not STEPS_FILE.exists():
        print(f"❌ 找不到步骤清单：{STEPS_FILE}", file=sys.stderr)
        sys.exit(2)
    return yaml.safe_load(STEPS_FILE.read_text(encoding="utf-8")) or {}


def load_steps() -> list:
    return load_config().get("steps") or []


def load_gate_items() -> list:
    """从 steps.yaml 展开门禁检查项：(路径, 说明, 关键字, 回退步骤)。"""
    items = []
    for step in load_steps():
        for art in step.get("artifacts") or []:
            items.append({
                "path": art["path"],
                "alt": art.get("alt") or [],
                "label": art.get("label", art["path"]),
                "keywords": art.get("keywords") or [],
                "launch_date": art.get("launch_date") or step.get("launch_date") or "",
                "fallback_steps": step.get("fallback") or [step["id"]],
            })
    return items


# 必交产物（由 workflow/steps.yaml 生成，改清单请改 yaml）
GATE_ITEMS = load_gate_items()
# 问题台账配置（同文件 ledger: 段）
LEDGER = load_config().get("ledger") or {}
# 设计→实施映射表配置（同文件 mapping: 段）
MAPPING = load_config().get("mapping") or {}


def _project_created_date(project_root: Path) -> str:
    """读看板「创建日期」，用于按上线日豁免历史项目的新增产物（同 mapping.launch_date 口径）。"""
    board = project_root / "_项目状态.md"
    if not board.exists():
        return ""
    text = board.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r"创建日期[：:]\s*(\d{4}-\d{2}-\d{2})", text)
    return m.group(1) if m else ""


def check_one(project_root: Path, item: dict) -> dict:
    # path 是主路径，alt 是历史项目可能用的旧路径（任一存在即算落盘）
    candidates = [item["path"]] + list(item.get("alt") or [])
    path = project_root / item["path"]
    for c in candidates:
        if (project_root / c).exists():
            path = project_root / c
            break
    result = {
        "path": item["path"],
        "label": item["label"],
        "exists": path.exists(),
        "size": path.stat().st_size if path.exists() else 0,
        "keywords_hit": None,
        "status": "MISSING",
    }

    # 新增产物带 launch_date：项目创建于上线日之前的，视为历史项目豁免，不判红
    launch = item.get("launch_date") or ""
    if launch:
        created = _project_created_date(project_root)
        if created and created < launch:
            result["status"] = "OK"
            result["skipped"] = f"历史项目（创建于 {created}，早于上线日 {launch}）"
            return result

    if not path.exists():
        result["status"] = "MISSING"
        return result

    if path.stat().st_size < 10:
        result["status"] = "EMPTY"
        return result

    kws = item.get("keywords") or []
    if kws:
        try:
            content = path.read_text(encoding="utf-8", errors="ignore").lower()
            hit = [kw for kw in kws if kw.lower() in content]
            result["keywords_hit"] = hit
            if not hit:
                result["status"] = "NO_KEYWORD"
                return result
        except Exception as e:
            result["status"] = f"READ_ERROR: {e}"
            return result

    result["status"] = "OK"
    return result


def check_board_consistency(root: Path) -> dict:
    """
    看板一致性检查（2026-10-28 新增，来源：10-27 晚看板未同步事故）。
    门禁全绿只代表产物文件都在；如果看板 _项目状态.md 还写着"进行中/未开始/当前卡点"，
    说明跑完没回写看板，必须先回写再改队列状态。
    """
    board = root / "_项目状态.md"
    info = {
        "path": "_项目状态.md",
        "label": "看板一致性（看板是否与产物同步）",
        "status": "OK",
        "details": "",
    }
    if not board.exists():
        info["status"] = "MISSING"
        info["details"] = "看板文件不存在"
        return info

    text = board.read_text(encoding="utf-8", errors="ignore")
    board_mtime = board.stat().st_mtime

    # 危险信号：看板还在说"进行中/未开始/当前卡点"
    danger_markers = [
        ("进行中", "看板仍标注[进行中]"),
        ("未开始", "看板仍标注[未开始]"),
        ("卡在人工", "看板仍标注[卡在人工]"),
        ("当前卡点", "看板仍写有[当前卡点]"),
        ("当前阶段：**", "看板[当前阶段]字段未更新为已闭环"),
    ]
    # 但要排除"已完成"语境：如"第6步 已完成"
    # 简单判定：如果看板文本里出现"项目已交付"/"已闭环"/"门禁全绿"等闭环词，就不算
    closed_markers = ["项目已交付", "已闭环", "门禁全绿", "项目完成", "MVP 验收通过"]
    is_closed_word = any(m in text for m in closed_markers)

    found_danger = []
    for marker, desc in danger_markers:
        if marker in text:
            # 如果同时有闭环词，且这个 marker 是表格里历史行的"未开始"（已被回写覆盖），不算
            # 粗判：只看"当前阶段"那一行
            if marker == "当前阶段：**":
                # 提取当前阶段行
                for line in text.splitlines():
                    if "当前阶段" in line:
                        if "已完成" in line or "已交付" in line or "闭环" in line:
                            break
                        else:
                            found_danger.append(desc)
                        break
            elif marker == "进行中":
                # 排除"已完成"行里的"进行中"（如"原标进行中"）
                # 只在"当前阶段"或"当前卡点"附近找
                if not is_closed_word:
                    found_danger.append(desc)
            else:
                if not is_closed_word:
                    found_danger.append(desc)

    if found_danger:
        info["status"] = "BOARD_STALE"
        info["details"] = "；".join(found_danger)

    # mtime 新鲜度：产物比看板新 >10 分钟，警告
    artifact_files = [root / it["path"] for it in GATE_ITEMS if (root / it["path"]).exists()]
    if artifact_files:
        newest_artifact = max(f.stat().st_mtime for f in artifact_files)
        age_min = (newest_artifact - board_mtime) / 60
        if age_min > 10:
            info["details"] += f"；最新产物比看板新 {age_min:.0f} 分钟，看板可能未回写"
            if info["status"] == "OK":
                info["status"] = "BOARD_FRESH_WARNING"

    return info


def check_ledger(root: Path, created_date: str | None = None) -> dict:
    """
    问题台账收敛检查（2026-10-29 新增，来源：第 7/8/9 步各写一份问题清单、状态互相不同步）。
    台账 `_问题台账.md` 是唯一问题清单；表格里还有 open/fixed 的 P0/P1 → 不许放行。

    按创建日期区分（方案 A）：
    - created_date < GATE_LAUNCH_DATE → 历史项目：无台账不阻塞（details 记一行）
    - created_date >= GATE_LAUNCH_DATE 或取不到日期 → 新项目：台账不存在视为阻塞
    """
    info = {
        "path": LEDGER.get("path", "_问题台账.md"),
        "label": "问题台账（P0/P1 必须全部 verified）",
        "status": "OK",
        "details": "",
        "fallback_steps": LEDGER.get("fallback") or ["7", "8", "9"],
    }
    if not LEDGER:
        return info
    f = root / info["path"]
    if not f.exists():
        if created_date and created_date < GATE_LAUNCH_DATE:
            info["details"] = "无台账（历史项目，不阻塞）"
            return info
        info["status"] = "LEDGER_MISSING"
        info["details"] = "新项目必须有 _问题台账.md；创建日期取不到时按新项目处理"
        return info

    block_levels = set(LEDGER.get("block_levels") or ["P0", "P1"])
    block_states = set(LEDGER.get("block_states") or ["open", "fixed"])
    text = f.read_text(encoding="utf-8", errors="ignore")
    # 去掉 HTML 注释（模板里的行示例在注释里，不能当成真问题）
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    blocking = []
    for line in text.splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.split("|")[1:-1]]
        if len(cells) < 8 or not re.match(r"^Q-\d+", cells[0]):
            continue
        if cells[1] in block_levels and cells[5] in block_states:
            blocking.append(f"{cells[0]}({cells[1]}/{cells[5]})")

    if blocking:
        info["status"] = "LEDGER_OPEN"
        shown = "、".join(blocking[:8]) + ("…" if len(blocking) > 8 else "")
        info["details"] = f"{len(blocking)} 条未收敛：{shown}"
    return info


def check_log_gap(root: Path) -> dict:
    """
    失败日志缺口警告（改进建议 #56，仅警告不阻塞）：
    台账里 P1 且状态 verified 的条数，应不大于 _失败日志.md 的记录条数；
    缺口 >0 说明「P1 修完没记失败日志」，R10 空转，step10 复盘会缺数据。
    """
    info = {
        "path": "_失败日志.md",
        "label": "失败日志缺口（P1 verified vs 失败日志条数）",
        "status": "OK",
        "details": "",
    }
    ledger_file = root / (LEDGER.get("path") or "_问题台账.md")
    log_file = root / "_失败日志.md"
    if not ledger_file.exists():
        info["details"] = "无台账，跳过"
        return info

    text = re.sub(r"<!--.*?-->", "", ledger_file.read_text(encoding="utf-8", errors="ignore"), flags=re.S)
    p1_verified = 0
    for line in text.splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.split("|")[1:-1]]
        if len(cells) >= 8 and re.match(r"^Q-\d+", cells[0]) and cells[1] == "P1" and cells[5] == "verified":
            p1_verified += 1

    log_rows = 0
    if log_file.exists():
        # 数据行两种形态：log_failure.py 写的 `| F-001 | 2026-…`，手写旧日志的 `| 2026-…`
        log_rows = sum(
            1 for l in log_file.read_text(encoding="utf-8", errors="ignore").splitlines()
            if re.match(r"\|\s*(F-\d+|2\d{3}-)", l)
        )

    gap = p1_verified - log_rows
    if gap > 0:
        info["status"] = "LOG_GAP_WARNING"
        info["details"] = f"台账 P1 verified {p1_verified} 条，失败日志仅 {log_rows} 条，缺口 {gap} 条"
    else:
        info["details"] = f"台账 P1 verified {p1_verified} 条 ≤ 失败日志 {log_rows} 条"
    return info


def check_mapping(root: Path, created_date: str | None) -> dict:
    """
    设计→实施 100% 映射核对（改进建议 #52④ + 用户 2026-10-30 硬要求）。
    上线日（steps.yaml mapping.launch_date）之前创建的项目豁免，避免把历史已交付项目判红。
    """
    map_path = MAPPING.get("path") or "_设计实施映射表.md"
    info = {
        "path": map_path,
        "label": "设计→实施 100% 映射（无 ❌未实现 / ⚠️未验证）",
        "status": "OK",
        "details": "",
        "fallback_steps": MAPPING.get("fallback") or ["4", "5A", "5B", "6"],
    }
    if not MAPPING:
        info["details"] = "steps.yaml 未配置 mapping 段，跳过"
        return info

    launch = MAPPING.get("launch_date") or ""
    if created_date and launch and created_date < launch:
        info["details"] = f"历史项目（创建于映射闸门上线前 {launch}），不阻塞"
        return info

    try:
        from design_impl_check import check_project
    except ImportError as e:
        info["status"] = "MAPPING_STRUCTURE"
        info["details"] = f"无法导入 design_impl_check.py：{e}"
        return info

    r = check_project(root, stage="10", mapping_path=map_path)
    if r["status"] == "OK":
        info["details"] = f"条目 {r['total']}：✅{r['verified']} / ⚠️{r['unverified']} / ❌{r['missing']} / ✂️{r['cut']}"
    else:
        info["status"] = r["status"]
        info["details"] = r["details"]
    return info


def main():
    ap = argparse.ArgumentParser(description="工作流完成门禁检查")
    ap.add_argument("project_dir", help="项目目录，如 projects/xxx")
    ap.add_argument("--json", action="store_true", help="输出 JSON（供 CI/脚本消费）")
    args = ap.parse_args()

    root = Path(args.project_dir).resolve()
    if not root.exists() or not root.is_dir():
        print(f"❌ 项目目录不存在：{root}", file=sys.stderr)
        sys.exit(2)

    # 豁免项目：跳过门禁，直接全绿
    project_name = root.name
    is_exempt, exempt_reason = _is_exempt(root.parent.parent, project_name)
    if is_exempt:
        summary = {
            "project": str(root),
            "exempted": True,
            "exempt_reason": exempt_reason,
            "all_green": True,
            "total": 0,
            "passed": 0,
            "failed": 0,
        }
        if args.json:
            print(json.dumps(summary, ensure_ascii=False, indent=2))
        else:
            print(f"🟢 项目已豁免门禁：{project_name}")
            print(f"   原因：{exempt_reason}")
            print("   （跳过 10 项产物检查 + 台账收敛 + 看板一致性）")
        sys.exit(0)

    # 读取项目创建日期（按方案 A 区分台账必查/可选）
    created_date = _read_project_create_date(root)

    results = [check_one(root, item) for item in GATE_ITEMS]
    # 追加问题台账收敛检查（按创建日期判断可选/必查）+ 看板一致性检查
    ledger_result = check_ledger(root, created_date)
    board_result = check_board_consistency(root)
    log_gap_result = check_log_gap(root)
    mapping_result = check_mapping(root, created_date)
    results.append(ledger_result)
    results.append(board_result)
    results.append(log_gap_result)
    results.append(mapping_result)
    failed = [r for r in results
              if r["status"] not in ("OK", "BOARD_FRESH_WARNING", "LOG_GAP_WARNING")]

    # 建议回退到的步骤：第一个失败项按 path 反查 GATE_ITEMS
    # （results 末尾追加了台账/看板项，长度与 GATE_ITEMS 不一致，不能用下标直接索引）
    suggested_fallback = None
    if failed:
        fallback_map = {it["path"]: it["fallback_steps"] for it in GATE_ITEMS}
        suggested_fallback = failed[0].get("fallback_steps") or fallback_map.get(failed[0]["path"])

    summary = {
        "project": str(root),
        "total": len(results),
        "passed": len(results) - len(failed),
        "failed": len(failed),
        "suggested_fallback_steps": suggested_fallback,
        "all_green": len(failed) == 0,
        "items": results,
    }

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"\n=== 工作流完成门禁检查：{root.name} ===\n")
        for r in results:
            icon = {
                "OK": "✅",
                "MISSING": "❌",
                "EMPTY": "⚠️ ",
                "NO_KEYWORD": "⚠️ ",
                "BOARD_STALE": "🔴",
                "BOARD_FRESH_WARNING": "🟡",
                "LOG_GAP_WARNING": "🟡",
                "LEDGER_OPEN": "🔴",
                "MAPPING_MISSING": "🔴",
                "MAPPING_EMPTY": "🔴",
                "MAPPING_STRUCTURE": "🔴",
                "MAPPING_NOT_READY": "🔴",
            }.get(r["status"], "💥")
            line = f"{icon} {r['label']:<28} {r['path']}"
            if r["status"] == "OK" and "size" in r:
                line += f"  ({r['size']}B)"
            elif r["status"] == "OK" and r.get("details"):
                line += f"  [{r['details']}]"
            elif r["status"] == "MISSING":
                line += "  [文件不存在]"
            elif r["status"] == "EMPTY":
                line += "  [文件为空]"
            elif r["status"] == "NO_KEYWORD":
                line += f"  [未命中关键字]"
            elif r["status"] == "BOARD_STALE":
                line += f"  [看板未同步：{r.get('details','')}]"
            elif r["status"] == "BOARD_FRESH_WARNING":
                line += f"  [看板可能未回写：{r.get('details','')}]"
            elif r["status"] == "LOG_GAP_WARNING":
                line += f"  [失败日志缺口（不阻塞）：{r.get('details','')}]"
            elif r["status"] == "LEDGER_OPEN":
                line += f"  [台账未收敛：{r.get('details','')}]"
            elif r["status"] in ("MAPPING_MISSING", "MAPPING_EMPTY", "MAPPING_STRUCTURE", "MAPPING_NOT_READY"):
                line += f"  [映射未 100%：{r.get('details','')}]"
            print(line)

        print()
        if summary["all_green"]:
            print("🟢 全部门禁通过。可以把队列状态改为「已完成」，并推送 GitHub。")
        else:
            print(
                f"🔴 {len(failed)}/{len(results)} 项未通过。"
                f"禁止把队列状态改为「已完成」。"
            )
            if board_result["status"] == "BOARD_STALE":
                print(f"   ⚠️ 看板未同步：{board_result.get('details','')}")
                print("   请先按实际进度回写 _项目状态.md，再重跑本脚本。")
            elif ledger_result["status"] == "LEDGER_OPEN":
                print(f"   ⚠️ 问题台账未收敛：{ledger_result.get('details','')}")
                print("   按附录 A 修完并回归，把台账状态改 verified，再重跑本脚本。")
            elif mapping_result["status"] != "OK":
                print(f"   ⚠️ 设计→实施映射未 100%：{mapping_result.get('details','')}")
                print("   按映射表补齐 ❌未实现 的功能链路，或把 ⚠️ 行按用户操作路径验证掉；"
                      "确实不做的标 ✂️ 并写砍掉依据。补齐后重跑本脚本。")
            elif suggested_fallback:
                print(f"   建议回退到步骤：{suggested_fallback}")
                print("   补齐缺失产物后重跑本脚本，全绿再推进。")

    sys.exit(0 if summary["all_green"] else 1)


if __name__ == "__main__":
    main()
