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
import os
import re
import sys
from pathlib import Path

STEPS_FILE = Path(__file__).resolve().parent.parent / "workflow" / "steps.yaml"
QUEUE_FILE = Path(__file__).resolve().parent.parent / "WORKFLOW_项目队列.md"
# 门禁上线日期：此日期前创建的项目，台账/10.6 为可选；之后的必查（方案 A，按创建日期切分）
GATE_LAUNCH_DATE = "2026-10-29"
# 看板严格回写上线日：此日期前创建的项目，看板滞后降级为警告（不阻塞历史项目）
BOARD_STRICT_DATE = "2026-11-11"
# 产物内容闸门默认值（steps.yaml 单个 artifact 可用 min_bytes 覆盖）
DEFAULT_MIN_BYTES = 32
# forbid 语境豁免词（#97）：命中禁词的同一行若含下列语境标记，视为「如实归属技术债 / 已修复根因 / 占位口径」，
# 不判结论性否定；只禁 Review 未通过 / 主流程未通 / P0 未清零 这类结论。
FORBID_CONTEXT_EXEMPT = [
    "deferred", "技术债", "已修复", "已改", "回归通过", "瑕疵", "根因", "历史瑕疵",
    "无 todo", "占位", "如实", "未验证", "边界", "降级", "砍除", "未做", "诚实", "标注",
]
# 看板「创建日期」兼容两种写法：
#   创建日期：2026-11-02
#   创建日期：**2026-11-02**（翻新建档）      ← 粗体 + 后缀说明，必须照样抓到日期
CREATE_DATE_RE = re.compile(r"创建日期[：:]\s*\**\s*(\d{4}-\d{2}-\d{2})")


def _parse_date(s: str) -> str:
    """从日期字符串里抽 YYYY-MM-DD。"""
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", s)
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else None


def _read_project_create_date(pdir: Path) -> str:
    """从项目看板取「创建日期」YYYY-MM-DD（兼容 `创建日期：**2026-11-02**（翻新建档）`）。取不到返回 None。"""
    board = pdir / "_项目状态.md"
    if not board.exists():
        return None
    m = CREATE_DATE_RE.search(board.read_text(encoding="utf-8", errors="ignore"))
    return m.group(1) if m else None


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


def _gate_item(art: dict, step: dict, is_refurbish: bool) -> dict:
    """把 steps.yaml 的一条 artifact 展开成门禁检查项（含内容闸门扩展键，缺省不启用）。"""
    return {
        "path": art["path"],
        "alt": art.get("alt") or [],
        "label": art.get("label", art["path"]),
        "keywords": art.get("keywords") or [],
        "launch_date": art.get("launch_date") or step.get("launch_date") or "",
        "fallback_steps": step.get("fallback") or [step["id"]],
        "is_refurbish": is_refurbish,
        "min_bytes": art.get("min_bytes", DEFAULT_MIN_BYTES),
        "forbid": art.get("forbid") or [],
        "optional": bool(art.get("optional")),
        "mode": art.get("mode") or "",
        "requires_frontend": bool(art.get("requires_frontend")),
        "requires_http_api": bool(art.get("requires_http_api")),
        "requires_skill": art.get("requires_skill") or "",
    }


def load_gate_items() -> list:
    """从 steps.yaml 展开门禁检查项：(路径, 说明, 关键字, 回退步骤)。
    F0/F1/F2 为翻新线专属步骤，仅当项目看板「路线=翻新」时返回其 artifacts。
    生产线项目（路线=生产或缺省）自动跳过 F0~F2。

    artifact 可选内容闸门键（缺省不启用）：
      - min_bytes：文件最小字节数，默认 32；小于判 EMPTY
      - forbid：禁用内容子串列表，命中任一判 NEGATIVE
      - optional + mode：仅当看板「设计模式」含 mode 时才要求该产物，否则返回 OK+skipped
    """
    items = []
    for step in load_steps():
        step_id = str(step["id"])
        is_refurbish_step = step_id.startswith("F")
        if is_refurbish_step:
            # 翻新线步骤的 artifacts 不在此处无条件展开——由 main() 按路线字段二次过滤
            continue
        for art in step.get("artifacts") or []:
            items.append(_gate_item(art, step, is_refurbish=False))
    return items


def load_refurbish_gate_items() -> list:
    """翻新线专属步骤的 artifacts（F0/F1/F2）。仅当看板「路线=翻新」时才并入 GATE_ITEMS。"""
    items = []
    for step in load_steps():
        step_id = str(step["id"])
        if not step_id.startswith("F"):
            continue
        for art in step.get("artifacts") or []:
            items.append(_gate_item(art, step, is_refurbish=True))
    return items


def _read_project_route(project_root: Path) -> str:
    """读看板「路线」字段。缺失默认 '生产'；显式写 '翻新' 返回 '翻新'。"""
    board = project_root / "_项目状态.md"
    if not board.exists():
        return "生产"
    text = board.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r"\*\*路线\*\*：\s*(生产|翻新)", text)
    return m.group(1) if m else "生产"


def _read_design_mode(project_root: Path) -> str:
    """读看板「设计模式」字段（如「普通模式（R24）」「精修模式」）。取不到返回空串。"""
    board = project_root / "_项目状态.md"
    if not board.exists():
        return ""
    text = board.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r"设计模式\*{0,2}[：:]\s*(.+)", text)
    return m.group(1).strip().strip("*").strip() if m else ""


def _normalize_design_mode(board_mode: str) -> str:
    """把看板设计模式说明归一化为枚举取值「精修」/「普通」/空（#99 精确匹配，不再子串包含）。

    否定语境优先：「无 UI 精修需求」「不精修」「非精修」「普通」都归普通，
    避免说明文字里出现「精修」二字就被误判成精修模式。
    """
    if not board_mode:
        return ""
    text = board_mode
    if re.search(r"无\s*UI?\s*精修|不精修|非精修|普通", text):
        return "普通"
    if "精修" in text:
        return "精修"
    return ""


def _has_http_api(project_root: Path) -> bool:
    """看板「接口形态」为二进制/非 HTTP 时返回 False；缺失默认 True（保守要求）。"""
    board = project_root / "_项目状态.md"
    if not board.exists():
        return True
    text = board.read_text(encoding="utf-8", errors="ignore")
    if re.search(r"接口形态\*{0,2}[：:]\s*(二进制|非\s*HTTP|Protobuf|KCP|WebSocket-only)", text):
        return False
    return True


def _has_skill(name: str) -> bool:
    """本机技能库是否存在（skills/ 被 gitignore，缺库时应显式降级而非误判缺产物）。"""
    root = Path(__file__).resolve().parent.parent
    return (root / "skills" / "active" / name).exists()


def _has_frontend(project_root: Path) -> bool:
    """判断项目是否带前端工程（#98）。

    依据看板：5B 前端开发行状态为「不适用」，或看板明确写「本项目无前端 / 无前端工程」→ 纯后端，返回 False；
    其余默认 True（保守：拿不准时仍按有前端查产物）。
    """
    board = project_root / "_项目状态.md"
    if not board.exists():
        return True
    text = board.read_text(encoding="utf-8", errors="ignore")
    if re.search(r"本项目无前端|无前端工程|纯后端", text):
        return False
    # 5B 行：`| 5B | 前端开发 | 不适用 | ...`
    for line in text.splitlines():
        if line.strip().startswith("|") and "5B" in line and "前端" in line:
            cells = [c.strip() for c in line.split("|")[1:-1]]
            if len(cells) >= 3 and cells[2] in ("不适用", "跳过", "N/A"):
                return False
    return True


# 必交产物（由 workflow/steps.yaml 生成，改清单请改 yaml）
GATE_ITEMS = load_gate_items()
# 问题台账配置（同文件 ledger: 段）
LEDGER = load_config().get("ledger") or {}
# 设计→实施映射表配置（同文件 mapping: 段）
MAPPING = load_config().get("mapping") or {}


def _project_created_date(project_root: Path) -> str:
    """读看板「创建日期」，用于按上线日豁免历史项目的新增产物（同 mapping.launch_date 口径）。
    兼容粗体写法 `创建日期：**2026-11-02**（翻新建档）`——此前只认无粗体，导致翻新项目豁免失效。"""
    board = project_root / "_项目状态.md"
    if not board.exists():
        return ""
    text = board.read_text(encoding="utf-8", errors="ignore")
    m = CREATE_DATE_RE.search(text)
    return m.group(1) if m else ""


def _scan_forbid(content: str, forbids: list[str]) -> list[str]:
    """逐行扫 forbid 词（#97）：命中行若带豁免语境（技术债/已修复/如实标注/占位等），不计结论性否定。

    跨语境不豁免——只看命中词所在那一行；返回去重后的命中禁词列表。
    """
    hits = []
    for line in content.splitlines():
        low_line = line.lower()
        matched = [f for f in forbids if f in line or f.lower() in low_line]
        if not matched:
            continue
        if any(ctx in low_line for ctx in FORBID_CONTEXT_EXEMPT):
            continue
        hits.extend(matched)
    # 去重保序
    seen = set()
    uniq = []
    for h in hits:
        if h not in seen:
            seen.add(h)
            uniq.append(h)
    return uniq


def check_one(project_root: Path, item: dict) -> dict:
    """校验单个产物：存在 + 体积 + 关键字（+ 禁用内容 / 可选模式）。

    返回 status：
      OK              通过（可带 skipped 说明为何跳过内容校验）
      MISSING         文件不存在
      EMPTY           文件小于 min_bytes（默认 32B）
      NO_KEYWORD      未命中任一 keywords（keywords 为空时不查）
      NEGATIVE        命中 forbid 中任一禁用内容（如「P0 未清零」「未通过」）
      READ_ERROR      文件读取失败
    """
    # path 是主路径，alt 是历史项目可能用的旧路径（任一存在即算落盘）
    candidates = [item["path"]] + list(item.get("alt") or [])
    path = project_root / item["path"]
    for c in candidates:
        if (project_root / c).exists():
            path = project_root / c
            break
    try:
        min_bytes = int(item.get("min_bytes", DEFAULT_MIN_BYTES))
    except (TypeError, ValueError):
        min_bytes = DEFAULT_MIN_BYTES
    result = {
        "path": item["path"],
        "label": item["label"],
        "exists": path.exists(),
        "size": path.stat().st_size if path.exists() else 0,
        "min_bytes": min_bytes,
        "keywords_hit": None,
        "forbid_hit": None,
        "status": "MISSING",
    }

    # 可选产物：只有看板「设计模式」等于指定模式时才要求（#99 精确匹配枚举，不再子串包含）
    optional_mode = (item.get("mode") or "").strip() if item.get("optional") else ""
    if optional_mode:
        board_mode = _read_design_mode(project_root)
        if _normalize_design_mode(board_mode) != optional_mode:
            result["skipped"] = f"看板「设计模式」为「{board_mode or '未填'}」，非{optional_mode}模式，跳过"
            result["details"] = result["skipped"]
            result["status"] = "OK"
            return result

    # 纯后端不适用产物（#98）：前端 UI / taste / OpenAPI 等 requires_frontend 条目，
    # 项目无前端时直接跳过，不判 MISSING；仍允许补「不适用登记占位」文件留痕。
    if item.get("requires_frontend") and not _has_frontend(project_root):
        result["skipped"] = "纯后端项目无前端工程，该产物不适用，跳过"
        result["details"] = result["skipped"]
        result["status"] = "OK"
        return result

    # 非 HTTP 接口形态（二进制/Protobuf/KCP 等）：无 OpenAPI 可导出，跳过（#98 补口）
    if item.get("requires_http_api") and not _has_http_api(project_root):
        result["skipped"] = "看板接口形态非 HTTP，无 OpenAPI 可导出，跳过"
        result["details"] = result["skipped"]
        result["status"] = "OK"
        return result

    # 依赖本机技能库的产物（如 taste 检测）：缺库时显式降级，不把「没装 skill」误判成「没交报告」
    if item.get("requires_skill") and not _has_skill(item["requires_skill"]):
        result["skipped"] = f"本机缺少技能库 {item['requires_skill']}，降级跳过"
        result["details"] = result["skipped"]
        result["status"] = "OK"
        return result

    # 新增产物带 launch_date：项目创建于上线日之前的，视为历史项目豁免，不判红
    launch = item.get("launch_date") or ""
    if launch:
        created = _project_created_date(project_root)
        if created and created < launch:
            result["status"] = "OK"
            result["skipped"] = f"历史项目（创建于 {created}，早于上线日 {launch}）"
            result["details"] = result["skipped"]
            return result

    if not path.exists():
        result["status"] = "MISSING"
        return result

    actual_size = path.stat().st_size
    if actual_size < min_bytes:
        result["status"] = "EMPTY"
        result["details"] = f"{actual_size}B < 阈值 {min_bytes}B"
        return result

    kws = item.get("keywords") or []
    forbids = [f for f in (item.get("forbid") or []) if f]
    if kws or forbids:
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            result["status"] = f"READ_ERROR: {e}"
            return result
        low = content.lower()
        if forbids:
            forbid_hit = _scan_forbid(content, forbids)
            result["forbid_hit"] = forbid_hit
            if forbid_hit:
                result["status"] = "NEGATIVE"
                result["details"] = f"命中禁用内容：{'、'.join(forbid_hit[:5])}"
                return result
        if kws:
            hit = [kw for kw in kws if kw.lower() in low]
            result["keywords_hit"] = hit
            if not hit:
                result["status"] = "NO_KEYWORD"
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
    # 表格状态列：只有明确完成态才算已回写（2026-11-11 起不再凭产物路径列跳过）
    done_states = ("已完成", "通过", "不适用", "闭环", "已交付")

    found_danger = []
    seen_danger = set()

    def _add(desc: str):
        if desc not in seen_danger:
            seen_danger.add(desc)
            found_danger.append(desc)

    for line in text.splitlines():
        stripped = line.strip()
        # 跳过 markdown 标题：段标题（如「## 当前卡点」）是固定模板结构，不是卡点正文
        if stripped.startswith("#"):
            continue
        # 跳过「状态取值：…」枚举说明行：列出合法状态词，不代表当前状态
        if "状态取值" in stripped:
            continue
        # 跳过模板字段的取值枚举行（如「总体状态：未开始 / 进行中 / …」），真实状态行不含斜杠枚举
        if "总体状态" in stripped and "/" in stripped:
            continue

        if stripped.startswith("|"):
            # 表格行：只解析状态列（第 3 列），产物路径/备注列里的词不算滞后
            cells = [c.strip() for c in stripped.split("|")[1:-1]]
            if len(cells) >= 3:
                state_col = cells[2]
                for marker, desc in danger_markers:
                    if marker == "当前阶段：**":
                        continue
                    if marker in state_col:
                        # 状态列已是完成态才跳过；「未开始 + 路径非空」照样判滞后
                        if any(s in state_col for s in done_states):
                            continue
                        _add(desc)
            continue

        # 非表格行：当前阶段行单独判；其余危险词不再受全局闭环词豁免
        for marker, desc in danger_markers:
            if marker not in line:
                continue
            if marker == "当前阶段：**":
                if "已完成" in line or "已交付" in line or "闭环" in line:
                    break
                _add(desc)
            else:
                _add(desc)

    if found_danger:
        created = _project_created_date(root)
        if created and created < BOARD_STRICT_DATE:
            info["status"] = "BOARD_FRESH_WARNING"
            info["details"] = "旧项目看板回写不严格，降级警告：" + "；".join(found_danger)
        else:
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
    交付阶段（stage 10）：✅ 行必须有「验证证据」（空/—/无/待补/TODO 判 MAPPING_EVIDENCE）；
    steps.yaml 的 mapping.min_rows 会传给 design_impl_check 做条数下限。
    """
    map_path = MAPPING.get("path") or "_设计实施映射表.md"
    info = {
        "path": map_path,
        "label": "设计→实施 100% 映射（无 ❌未实现 / ⚠️未验证 / ✅缺证据）",
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

    try:
        min_rows = int(MAPPING.get("min_rows") or 0)
    except (TypeError, ValueError):
        min_rows = 0
    r = check_project(root, stage="10", mapping_path=map_path, min_rows=min_rows)
    if r["status"] == "OK":
        info["details"] = (f"条目 {r['total']}（min_rows={min_rows}）："
                           f"✅{r['verified']} / ⚠️{r['unverified']} / ❌{r['missing']} / ✂️{r['cut']}")
    else:
        info["status"] = r["status"]
        info["details"] = r["details"]
    return info


def check_job_handoff(project_name: str) -> dict:
    """
    求职侧联动（2026-11-07 新增，用户硬要求）：
    项目做完后，扫 JD 仓库下所有状态为「⏳等项目」的 JD，看有没有在等当前项目。
    JD 仓库路径由环境变量 WORKFLOW_JD_REPO 指定；未配置则静默跳过（不写死本机路径）。
    INFO 级，不阻塞门禁。
    """
    info = {
        "path": "(求职侧联动)",
        "label": "求职侧联动扫描",
        "status": "OK",
        "details": "",
    }
    jd_env = os.environ.get("WORKFLOW_JD_REPO", "").strip()
    if not jd_env:
        info["details"] = "JD仓库未配置（设 WORKFLOW_JD_REPO 环境变量启用），跳过"
        return info
    jd_dir = Path(jd_env).expanduser()
    if not jd_dir.exists():
        info["details"] = f"JD仓库不存在（{jd_dir}），跳过"
        return info

    waiting_jds = []
    for md in jd_dir.glob("*.md"):
        if md.name.startswith("_") or md.name == "README.md":
            continue
        text = md.read_text(encoding="utf-8", errors="ignore")
        if "⏳" not in text and "等项目" not in text:
            continue
        # 解析待补项目 checkbox 行
        pending = []
        for line in text.splitlines():
            m = re.match(r"\s*-\s*\[\s[ xX]\s*\]\s*(.+)", line)
            if m:
                pending.append(m.group(1).strip())
        if pending:
            waiting_jds.append((md.stem, pending))

    if not waiting_jds:
        info["details"] = "无等待中的 JD"
        return info

    # 找哪些 JD 在等当前项目
    matched = []
    for jd_name, pending in waiting_jds:
        for p in pending:
            # 项目名可能是 pending 行的子串，反之亦然
            if project_name.lower() in p.lower() or p.lower() in project_name.lower():
                matched.append((jd_name, pending))
                break

    if matched:
        lines = [f"项目「{project_name}」被 {len(matched)} 个 JD 在等："]
        for jd_name, pending in matched:
            remaining = [p for p in pending if project_name.lower() not in p.lower()]
            if remaining:
                lines.append(f"  ⏳ {jd_name} → 还在等: {', '.join(remaining)}")
                lines.append(f"     → 要不要把下一个排进队列？")
            else:
                lines.append(f"  ✅ {jd_name} → 等的项目全齐了，可以去求职侧出简历")
        info["details"] = "；".join(lines)
        info["status"] = "JOB_HANDOFF"
    else:
        info["details"] = f"有 {len(waiting_jds)} 个 JD 在等其他项目，与本项目无关"
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

    # 读看板路线字段：生产线查 GATE_ITEMS；翻新线追加 load_refurbish_gate_items()
    route = _read_project_route(root)
    gate_items = list(GATE_ITEMS)  # 生产线全部 items
    if route == "翻新":
        gate_items.extend(load_refurbish_gate_items())

    results = [check_one(root, item) for item in gate_items]
    # 追加问题台账收敛检查（按创建日期判断可选/必查）+ 看板一致性检查
    ledger_result = check_ledger(root, created_date)
    board_result = check_board_consistency(root)
    log_gap_result = check_log_gap(root)
    mapping_result = check_mapping(root, created_date)
    job_handoff_result = check_job_handoff(project_name)
    results.append(ledger_result)
    results.append(board_result)
    results.append(log_gap_result)
    results.append(mapping_result)
    results.append(job_handoff_result)
    failed = [r for r in results
              if r["status"] not in ("OK", "BOARD_FRESH_WARNING", "LOG_GAP_WARNING", "JOB_HANDOFF")]

    # 建议回退到的步骤：第一个失败项按 path 反查 gate_items（含翻新 items）
    suggested_fallback = None
    if failed:
        fallback_map = {it["path"]: it["fallback_steps"] for it in gate_items}
        suggested_fallback = failed[0].get("fallback_steps") or fallback_map.get(failed[0]["path"])

    summary = {
        "project": str(root),
        "total": len(results),
        "passed": len(results) - len(failed),
        "skipped": sum(1 for r in results if r.get("skipped")),
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
                "NEGATIVE": "🔴",
                "BOARD_STALE": "🔴",
                "BOARD_FRESH_WARNING": "🟡",
                "LOG_GAP_WARNING": "🟡",
                "JOB_HANDOFF": "📮",
                "LEDGER_OPEN": "🔴",
                "MAPPING_MISSING": "🔴",
                "MAPPING_EMPTY": "🔴",
                "MAPPING_STRUCTURE": "🔴",
                "MAPPING_NOT_READY": "🔴",
                "MAPPING_EVIDENCE": "🔴",
            }.get(r["status"], "💥")
            line = f"{icon} {r['label']:<28} {r['path']}"
            if r["status"] == "OK" and r.get("skipped"):
                line += f"  [跳过：{r['skipped']}]"
            elif r["status"] == "OK" and "size" in r and r.get("exists"):
                line += f"  ({r['size']}B)"
            elif r["status"] == "OK" and r.get("details"):
                line += f"  [{r['details']}]"
            elif r["status"] == "MISSING":
                line += "  [文件不存在]"
            elif r["status"] == "EMPTY":
                line += f"  [文件过小：{r.get('details') or '未达 min_bytes'}]"
            elif r["status"] == "NO_KEYWORD":
                line += f"  [未命中关键字]"
            elif r["status"] == "NEGATIVE":
                line += f"  [{r.get('details','')}]"
            elif r["status"] == "BOARD_STALE":
                line += f"  [看板未同步：{r.get('details','')}]"
            elif r["status"] == "BOARD_FRESH_WARNING":
                line += f"  [看板可能未回写：{r.get('details','')}]"
            elif r["status"] == "LOG_GAP_WARNING":
                line += f"  [失败日志缺口（不阻塞）：{r.get('details','')}]"
            elif r["status"] == "JOB_HANDOFF":
                line += f"  [求职侧联动：{r.get('details','')}]"
            elif r["status"] == "LEDGER_OPEN":
                line += f"  [台账未收敛：{r.get('details','')}]"
            elif r["status"] in ("MAPPING_MISSING", "MAPPING_EMPTY", "MAPPING_STRUCTURE",
                                 "MAPPING_NOT_READY", "MAPPING_EVIDENCE"):
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
                if mapping_result["status"] == "MAPPING_EVIDENCE":
                    print("   ✅ 行「验证证据」必须写实测证据（接口返回/截图路径/日志片段），"
                          "不能是空/—/无/待补/TODO。补证据后重跑本脚本。")
                else:
                    print("   按映射表补齐 ❌未实现 的功能链路，或把 ⚠️ 行按用户操作路径验证掉；"
                          "确实不做的标 ✂️ 并写砍掉依据。补齐后重跑本脚本。")
            elif suggested_fallback:
                print(f"   建议回退到步骤：{suggested_fallback}")
                print("   补齐缺失产物后重跑本脚本，全绿再推进。")

    sys.exit(0 if summary["all_green"] else 1)


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
