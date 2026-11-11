#!/usr/bin/env python3
"""
wf — 从 0 到 1 项目自动工作流命令行工具

命令：
  wf init <项目名> [--desc "原始描述" | --desc-file 路径]   从模板创建新项目
  wf list                                                    列出所有项目
  wf status [项目名]                                          查看项目进度看板
  wf next [项目名]                                            当前步骤 + 应使用的提示词模板
  wf prompt <步骤号>                                          打印指定步骤的提示词模板（如 wf prompt 6 / wf prompt 8.5 / wf prompt 0.1）
  wf advance <项目名> <阶段描述>                              更新看板「当前阶段」
  wf queue [--sync | --check [--allow-missing]]               队列事实列：从看板+门禁推导 / 回写 / 校验
  wf log <项目名> --step N --category ... --desc ...         记录失败日志
  wf check deps <路径>                                       依赖版本真实性校验
  wf check secrets <路径>                                    硬编码密钥扫描
  wf check contract export <url> <输出路径>                  导出后端 OpenAPI 契约
  wf check contract check <契约路径> <前端目录>               校验前端调用符合契约
  wf check regression <p0_cases.json>                        P0 自动化回归测试

工作流根目录识别：从当前目录向上查找含 WORKFLOW_工作流主控.md 的目录。
"""

import argparse
import datetime
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT_MARKER = "WORKFLOW_工作流主控.md"
TEMPLATE_NAME = "_TEMPLATE_新项目"
QUEUE_FILE = "WORKFLOW_项目队列.md"

# 2026-11-09：主控已瘦身为 <100 行指针文件，规则正文拆到专项文件。
# 一致性校验的事实源随之改到下面四份文件，主控只保留「总执行顺序」流程图。
# 改章节标题时，必须同步改本文件的解析正则，否则 wf steps --check 会整片报红。
STEPDEF_FILE = "WORKFLOW_步骤定义.md"
RULEBOOK_FILE = "WORKFLOW_规则库.md"
GATE_FILE = "WORKFLOW_卡点协议.md"
EXEC_FILE = "WORKFLOW_执行约定.md"

# 设计模块 0.1~0.5：不写进 steps.yaml 的 steps 列表（没有项目看板，走 projects/_队列/），
# steps.yaml 的 design_module 段登记它；此处是段缺失时的兜底，命名与 WORKFLOW_步骤定义.md 一致。
DESIGN_MODULE_FALLBACK = [
    {"id": "0.1", "name": "JD 结构化拆解", "prompt": "step00_1_拆解JD.md"},
    {"id": "0.2", "name": "作品集画像扫描", "prompt": "step00_2_建画像库.md"},
    {"id": "0.3", "name": "缺口分析", "prompt": None},
    {"id": "0.4", "name": "候选选题矩阵", "prompt": "step00_3_选题设计.md"},
    {"id": "0.5", "name": "一页纸项目设计书", "prompt": None},
]
DESIGN_MODULE_IDS = {str(d["id"]) for d in DESIGN_MODULE_FALLBACK}
# WORKFLOW_步骤定义.md 步骤表里反引号包着的提示词文件名（只认 prompts/ 下的 stepXX_*.md）
PROMPT_REF_RE = re.compile(r"`(step[^`\s/]*\.md)`")
# 规则引用 R<数字> / R-<数字>（前后不能沾字母数字，避免误伤 CR2 这类标识）
RULE_REF_RE = re.compile(r"(?<![A-Za-z0-9_])R(-?\d+)(?!\d)")
# 区间写法 R1~R21（~ 或全角 ～）
RULE_RANGE_RE = re.compile(r"(?<![A-Za-z0-9_])R(\d+)\s*[~～]\s*R(\d+)(?!\d)")


def find_root() -> Path:
    """从当前目录向上查找工作流根目录"""
    d = Path.cwd().resolve()
    for _ in range(10):
        if (d / ROOT_MARKER).exists():
            return d
        if d.parent == d:
            break
        d = d.parent
    print(f"❌ 未找到工作流根目录（缺少 {ROOT_MARKER}）。请在工作流目录内运行，或 cd 到该目录。")
    sys.exit(1)


def project_dir(root: Path, name: str) -> Path:
    p = root / "projects" / name
    if not p.exists():
        print(f"❌ 项目不存在：{p}")
        sys.exit(1)
    return p


def _load_config(root: Path) -> dict:
    """读取 workflow/steps.yaml 全文（步骤单一事实源）。"""
    f = root / "workflow" / "steps.yaml"
    if not f.exists():
        return {}
    try:
        import yaml
    except ImportError:
        print("❌ 缺少 PyYAML，请先 pip install pyyaml")
        sys.exit(2)
    return yaml.safe_load(f.read_text(encoding="utf-8")) or {}


def _load_steps(root: Path) -> list:
    """读取 workflow/steps.yaml 的 steps 段。"""
    return _load_config(root).get("steps") or []


def _design_module(root: Path) -> list:
    """读取 steps.yaml 的 design_module 段（设计模块 0.1~0.5）；未登记时用内置兜底。"""
    dm = _load_config(root).get("design_module")
    return dm if isinstance(dm, list) and dm else list(DESIGN_MODULE_FALLBACK)


def step_to_prompt(root: Path, step: str) -> Path:
    """步骤号 -> prompts/ 下的模板文件（优先读 steps.yaml，未登记时按命名兜底）"""
    # 设计模块 0.1~0.5 不在 steps 列表里，先查 design_module 段，不能因 0.x 未登记 steps 就报错
    for dm in _design_module(root):
        if str(dm.get("id", "")).upper() == step.upper():
            name = dm.get("name") or "设计模块"
            if not dm.get("prompt"):
                print(f"第 {step} 步（{name}）无模板，按 WORKFLOW_步骤定义.md §3.1 执行（基于上游产物直接分析）。")
                sys.exit(0)
            f = root / "prompts" / dm["prompt"]
            if f.exists():
                return f
            print(f"❌ 第 {step} 步（{name}）声明的提示词不存在：{f}")
            sys.exit(1)

    for s in _load_steps(root):
        if str(s["id"]).upper() == step.upper():
            if not s.get("prompt"):
                print(f"第 {step} 步（{s['name']}）无提示词模板，按 WORKFLOW_步骤定义.md 步骤表用脚本/命令执行。")
                sys.exit(0)
            f = root / "prompts" / s["prompt"]
            if f.exists():
                return f
            print(f"❌ 第 {step} 步在 steps.yaml 中声明的提示词不存在：{f}")
            sys.exit(1)

    prompts = root / "prompts"
    if step.upper() in ("5A", "5B"):
        f = prompts / ("step05A_后端开发.md" if step.upper() == "5A" else "step05B_前端开发.md")
        if f.exists():
            return f
    if step in ("8.5",):
        f = prompts / "step08_5_安全扫描.md"
        if f.exists():
            return f
    matches = sorted(prompts.glob(f"step{int(float(step)):02d}_*.md"))
    if matches:
        return matches[0]
    print(f"❌ 找不到第 {step} 步的提示词模板（先用 wf steps 看已登记步骤）")
    sys.exit(1)


# ---------- 队列事实列推导 ----------

def _load_gate_module(root: Path):
    """复用门禁脚本的产物清单与检查逻辑，避免第二份 GATE_ITEMS。"""
    sys.path.insert(0, str(root / "scripts"))
    import workflow_completion_check as gate  # noqa: E402
    return gate


def _read_board(pdir: Path) -> dict:
    """从看板提取推导状态所需的事实：当前阶段、第 11 步是否完成、完成日期、卡点、搁置标记。"""
    info = {"exists": False, "stage": "", "step11_done": False,
            "dates": [], "checkpoint": "", "shelved": False, "closed": False}
    board = pdir / "_项目状态.md"
    if not board.exists():
        return info
    info["exists"] = True
    text = board.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r"当前阶段：\*\*(.+?)\*\*", text)
    info["stage"] = m.group(1) if m else ""
    info["shelved"] = "搁置" in text

    for line in text.splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.split("|")[1:-1]]
        if len(cells) < 5:
            continue
        if cells[0] in ("10.0", "10", "11"):
            d = re.search(r"\d{4}-\d{2}-\d{2}", cells[4] if len(cells) > 4 else "")
            if d:
                info["dates"].append(d.group(0))
            if cells[0] == "11" and "完成" in cells[2]:
                info["step11_done"] = True

    block = re.search(r"## 当前卡点（需要用户做什么）\s*\n(.*?)(?=\n## |\Z)", text, re.S)
    if block:
        # 忽略以 > 开头的说明性引用行，只取真实卡点内容
        body = " ".join(
            l.strip().lstrip("-").strip()
            for l in block.group(1).strip().splitlines()
            if l.strip() and not l.strip().startswith(">")
        )
        info["checkpoint"] = "" if (not body or "无卡点" in body or body == "无") else body[:60].replace("|", "／")
    info["closed"] = any(w in text for w in ("项目已交付", "已闭环", "门禁全绿", "项目完成", "MVP 验收通过"))
    return info


def _infer_facts(root: Path, name: str, gate, current_state: str = "") -> dict:
    """推导队列事实列。date/checkpoint 为 None 表示沿用原值（如待开工项目的计划备注）。
    current_state 为队列行现有状态；若为「已搁置」且项目无生产目录，保留已搁置不覆盖。
    完成判据与 10.0 门禁同口径：产物齐套 + 问题台账收敛 + 设计→实施映射 100%，
    任一不 OK 都不得推导为「已完成」（禁止只看产物存在就算完成）。"""
    pdir = root / "projects" / name
    if not pdir.exists():
        # 预备仓库项目（projects/_队列/<名>/）：若无生产目录且队列已标「已搁置」，保留
        qdir = root / "projects" / "_队列" / name
        if current_state.strip() == "已搁置":
            return {"state": "已搁置", "date": None, "checkpoint": None}
        if not qdir.exists():
            return {"state": "待开工", "date": None, "checkpoint": None}
        # 预备仓库有待开工项目
        return {"state": "待开工", "date": None, "checkpoint": None}
    b = _read_board(pdir)
    if b["shelved"]:
        return {"state": "已搁置", "date": None, "checkpoint": "见看板搁置说明"}

    # 豁免项目：直接返回，不跑门禁
    is_exempt, exempt_reason = gate._is_exempt(root, name)
    if is_exempt:
        date = b["dates"][0] if b["dates"] else None
        return {"state": "已豁免", "date": date, "checkpoint": exempt_reason or "见豁免清单"}

    # 门禁项与 10.0 脚本同口径：生产线全部 items；看板「路线=翻新」时追加翻新线专属 items
    gate_items = list(gate.GATE_ITEMS)
    route_fn = getattr(gate, "_read_project_route", None)
    refurb_fn = getattr(gate, "load_refurbish_gate_items", None)
    if route_fn is not None and refurb_fn is not None and route_fn(pdir) == "翻新":
        gate_items.extend(refurb_fn())
    artifacts_ok = all(gate.check_one(pdir, it)["status"] == "OK" for it in gate_items)
    board_status = gate.check_board_consistency(pdir)["status"]

    # 复用完成门禁脚本的门禁项：问题台账（P0/P1 必须收敛）+ 设计→实施映射（100%）
    created_fn = getattr(gate, "_read_project_create_date", None)
    created = created_fn(pdir) if created_fn is not None else ""
    ledger_res = gate.check_ledger(pdir, created)
    mapping_res = gate.check_mapping(pdir, created)
    gate_reds = []
    if ledger_res["status"] != "OK":
        gate_reds.append("问题台账未过：" + (ledger_res.get("details") or ledger_res["status"]))
    if mapping_res["status"] != "OK":
        gate_reds.append("映射表未过：" + (mapping_res.get("details") or mapping_res["status"]))

    date = b["dates"][0] if b["dates"] else None
    if artifacts_ok and gate_reds:
        # 产物看似齐了，但台账/映射门禁没绿——不能算完成，把红色原因写进卡点列
        checkpoint = "；".join(gate_reds)[:60].replace("|", "／")
        return {"state": "⚠ 门禁未通过", "date": date, "checkpoint": checkpoint}
    if artifacts_ok and board_status == "BOARD_STALE":
        return {"state": "⚠ 看板未同步", "date": date, "checkpoint": "产物已齐但看板未回写"}
    if artifacts_ok:
        return {"state": "已完成", "date": date, "checkpoint": "无（门禁全绿）"}
    if b["closed"]:
        # 门禁脚本上线（2026-10-27）之前完成的项目：看板明确已交付，但凑不齐当前 11 项产物
        return {"state": "已完成（未过门禁）", "date": date,
                "checkpoint": "历史项目，未跑完成门禁"}
    stage = b["stage"] or "未知阶段"
    return {"state": f"进行中（{stage}）", "date": None,
            "checkpoint": b["checkpoint"] or "—"}


def _queue_rows(root: Path):
    """解析队列表：返回 (文件路径, 原始行, [(行号, 单元格列表)])。
    9 列：项目名 | 路线 | 业务一句话 | 设计书路径 | 状态 | 来源 JD | 启动日期 | 完成日期 | 当前卡点。"""
    path = root / QUEUE_FILE
    lines = path.read_text(encoding="utf-8").splitlines()
    rows = []
    for i, line in enumerate(lines):
        if not line.strip().startswith("|"):
            continue
        cells = line.split("|")[1:-1]
        if len(cells) != 9:
            continue
        name = cells[0].strip()
        if not name or name == "项目名" or set(name) <= set("-: "):
            continue
        rows.append((i, cells))
    return path, lines, rows


def _print_missing(missing):
    """--allow-missing：汇总跳过的本地不存在项目（不算失败）。"""
    if missing:
        print(f"ℹ️ 跳过 {len(missing)} 个本地不存在的项目（--allow-missing）：{'、'.join(missing)}")


def cmd_queue(args):
    root = find_root()
    gate = _load_gate_module(root)
    path, lines, rows = _queue_rows(root)
    diffs = []
    missing = []
    for idx, cells in rows:
        name = cells[0].strip()
        # CI 用：projects/ 下没有该目录的队列行不参与比对（prepare 仓库/异地检出常见），不算失败
        if args.allow_missing and not (root / "projects" / name).exists():
            missing.append(name)
            continue
        current_state = cells[4].strip() if len(cells) > 4 else ""
        if args.check and current_state == "已搁置":
            continue  # 已搁置是人工判断，--check 不做推导比对（改进建议 #67）
        facts = _infer_facts(root, name, gate, current_state)
        new_cells = list(cells)
        changed = []
        if cells[4].strip() != facts["state"]:
            changed.append(("状态", cells[4].strip(), facts["state"]))
            new_cells[4] = f" {facts['state']} "
        if facts["date"] and cells[7].strip() != facts["date"]:
            changed.append(("完成日期", cells[7].strip(), facts["date"]))
            new_cells[7] = f" {facts['date']} "
        if facts["checkpoint"] and cells[8].strip() != facts["checkpoint"]:
            changed.append(("当前卡点", cells[8].strip(), facts["checkpoint"]))
            new_cells[8] = f" {facts['checkpoint']} "
        if changed:
            diffs.append((name, changed))
            if args.sync:
                lines[idx] = "|" + "|".join(new_cells) + "|"

    if args.check:
        if not diffs:
            print("🟢 队列事实列与看板/门禁一致。")
            _print_missing(missing)
            sys.exit(0)
        print("🔴 队列事实列已过期（状态/完成日期/当前卡点禁止手改）：")
        for name, changed in diffs:
            for field, old, new in changed:
                print(f"   - {name} · {field}：表里是「{old}」，推导应为「{new}」")
        print("   → 运行 wf queue --sync 回写")
        _print_missing(missing)
        sys.exit(1)

    if args.sync:
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"✅ 队列已回写：{path.name}（事实列 {len(diffs)} 处更新）")
        for name, changed in diffs:
            print(f"   - {name}：" + "；".join(f"{f}: {o} → {n}" for f, o, n in changed))
        _print_missing(missing)
        return

    for name, changed in diffs:
        print(f"  {name}：" + "；".join(f"{f}: {o} → {n}" for f, o, n in changed))
    print(f"\n共 {len(diffs)} 个项目的事实列与看板不一致。运行 wf queue --sync 回写，或 --check 用于 CI。")
    _print_missing(missing)


def cmd_steps(args):
    """列出 / 校验 steps.yaml：提示词、fallback、看板模板与各专项文件是否对得上。

    事实源（2026-11-09 起，主控瘦身为指针文件后）：
      步骤表 / 翻新线协议 → WORKFLOW_步骤定义.md
      8.0 登记表 / 规则正文 / 休眠区 → WORKFLOW_规则库.md
      R-1/R-2 卡点落点 → WORKFLOW_卡点协议.md
      总执行顺序流程图 → WORKFLOW_工作流主控.md
    """
    root = find_root()
    steps = _load_steps(root)
    if not steps:
        print("❌ workflow/steps.yaml 缺失或为空")
        sys.exit(2)

    if not args.check:
        print(f"{'步骤':<6}{'owner':<9}{'名称':<26}提示词")
        for s in steps:
            print(f"{str(s['id']):<6}{str(s.get('owner','')):<9}{s['name']:<26}{s.get('prompt') or '—'}")
        return

    errors = []

    def _read(name):
        p = root / name
        if not p.exists():
            errors.append(f"专项文件缺失：{name}（一致性校验无法进行）")
            return ""
        return p.read_text(encoding="utf-8")

    main_text = _read(ROOT_MARKER)
    stepdef_text = _read(STEPDEF_FILE)
    rulebook_text = _read(RULEBOOK_FILE)
    gates_text = _read(GATE_FILE)
    exec_text = _read(EXEC_FILE)
    ids = [str(s["id"]) for s in steps]
    if len(ids) != len(set(ids)):
        errors.append("步骤 id 重复")
    id_set = set(ids)
    design = _design_module(root)
    design_ids = {str(d.get("id")) for d in design}
    if design_ids != DESIGN_MODULE_IDS:
        errors.append("design_module 段的步骤 id 必须正好是 0.1~0.5，实际：" + "、".join(sorted(design_ids)))
    design_prompt_files = {dm["prompt"] for dm in design if dm.get("prompt")}
    for dm in design:
        if dm.get("prompt") and not (root / "prompts" / dm["prompt"]).exists():
            errors.append(f"设计模块 {dm.get('id')}: 提示词不存在 prompts/{dm['prompt']}")
    for s in steps:
        sid = str(s["id"])
        for fb in s.get("fallback") or []:
            if str(fb) not in id_set:
                errors.append(f"{sid}: fallback 指向未登记步骤 {fb}")
        p = s.get("prompt")
        if p and not (root / "prompts" / p).exists():
            errors.append(f"{sid}: 提示词不存在 prompts/{p}")
        for art in s.get("artifacts") or []:
            if not art.get("path"):
                errors.append(f"{sid}: artifacts 缺少 path")
            if art.get("keywords") and not art.get("forbid"):
                errors.append(
                    f"{sid}/{art.get('path', '?')}: 带 keywords 的产物必须配 forbid"
                    "（防「未通过」命中「通过」的否定式绕过）"
                )

    # 步骤编排表 ↔ steps.yaml/design_module 双向集合：多行少行都报红
    # 事实源 = WORKFLOW_步骤定义.md「一、生产线步骤编排表」+「二、翻新线步骤」两张表
    step_tables = re.search(r"^## 一、.*?(?=^## 三、)", stepdef_text, re.M | re.S)
    step2_ids = set()
    if not step_tables:
        errors.append(
            "步骤编排表解析失败（找不到 WORKFLOW_步骤定义.md 的「一、生产线步骤编排表」~「三、双模块协议」区间）"
        )
    else:
        for line in step_tables.group(0).splitlines():
            if not line.strip().startswith("|"):
                continue
            cells = [c.strip() for c in line.split("|")[1:-1]]
            if not cells:
                continue
            first = cells[0].replace("**", "").strip()
            if re.fullmatch(r"F\d+|\d+(?:\.\d+)?[AB]?", first):
                step2_ids.add(first)
        expected_ids = id_set | design_ids
        if not step2_ids:
            errors.append("步骤编排表解析失败（未识别到任何步骤 id）")
        else:
            only_main = sorted(step2_ids - expected_ids)
            only_yaml = sorted(expected_ids - step2_ids)
            if only_main:
                errors.append("步骤定义表有但 steps.yaml/design_module 未登记：" + "、".join(only_main))
            if only_yaml:
                errors.append("steps.yaml/design_module 有但步骤定义表缺行：" + "、".join(only_yaml))
        # 提示词存在性：步骤表里反引号包着的 stepXX_*.md 必须真在 prompts/ 下
        # （design_module 段已单独校验过的文件不重复报）
        for fname in sorted(set(PROMPT_REF_RE.findall(step_tables.group(0)))):
            if fname in design_prompt_files:
                continue
            if not (root / "prompts" / fname).exists():
                errors.append(f"步骤定义表引用的提示词不存在：prompts/{fname}")

    # 问题台账：模板里必须有该文件，fallback 必须指向已登记步骤
    ledger = _load_config(root).get("ledger") or {}
    if ledger:
        lp = ledger.get("path")
        if not lp:
            errors.append("ledger 段缺少 path")
        elif not (root / "projects" / TEMPLATE_NAME / lp).exists():
            errors.append(f"ledger: 模板项目缺少 {lp}")
        for fb in ledger.get("fallback") or []:
            if str(fb) not in id_set:
                errors.append(f"ledger: fallback 指向未登记步骤 {fb}")

    # 8.0 登记表 vs 规则实体（正文活跃 ∪ 休眠区）一致。
    # 关键：休眠不是删除——规则休眠后从正文移入休眠区（条目标题 "R<id> …（休眠于…）"），
    # 登记表行必须保留（id 不回收）。三方 id 集合必须相等，缺一报红。
    table_ids = set(re.findall(r"^\| R(\d+) \|", rulebook_text, re.M))
    section_rules = re.search(r"^## 规则正文.*?(?=^### 休眠规则|\Z)", rulebook_text, re.M | re.S)
    body_ids, dormant_ids = set(), set()
    if section_rules:
        # 正文活跃规则标题 "N. **"，休眠区已用前瞻排除
        body_ids = set(re.findall(r"^(\d+)\. \*\*", section_rules.group(0), re.M))
    dormant_block = re.search(r"^### 休眠规则.*", rulebook_text, re.M | re.S)
    if dormant_block:
        for line in dormant_block.group(0).splitlines():
            if line.strip().startswith(">"):  # 跳过说明性引用行（含 "R1–R25" 这类口径说明）
                continue
            dormant_ids.update(re.findall(r"\bR(\d+)\b", line))
    entity_ids = body_ids | dormant_ids
    if not table_ids or not section_rules:
        errors.append("规则登记表或规则正文解析失败（WORKFLOW_规则库.md）")
    elif table_ids != entity_ids:
        only_table = sorted(table_ids - entity_ids, key=int)
        only_entity = sorted(entity_ids - table_ids, key=int)
        if only_table:
            errors.append(
                f"8.0 登记表有 R{','.join(only_table)} 但正文和休眠区都没有"
                "（id 不回收：要么移回正文，要么移入休眠区，不许只删正文）"
            )
        if only_entity:
            errors.append(
                f"正文/休眠区有 R{','.join(only_entity)} 但 8.0 登记表缺行"
                "（新增/休眠规则必须先补登记表）"
            )

    # 规则引用 lint：主控 / 专项文件 / prompts / steps.yaml / scripts 里出现的 R<id>
    # （含 R-1 这类负号 id）必须都在 8.0 登记表里；允许 R1~R21 区间写法（展开后逐个校验）。
    sec80 = re.search(r"^## 8\.0 .*?(?=^## )", rulebook_text, re.M | re.S)
    rule_ids = set()
    if not sec80:
        errors.append("8.0 规则登记表解析失败（找不到 WORKFLOW_规则库.md 的 ## 8.0 小节）")
    else:
        rule_ids = set(re.findall(r"^\| (R-?\d+) \|", sec80.group(0), re.M))
        if not rule_ids:
            errors.append("8.0 规则登记表解析失败（未识别到任何 R<id> 行）")

    # 翻新线 R-1/R-2 单独校验：8.0 必须有登记行，且步骤定义 §3.4 协议 / 卡点协议卡点表都要有落点引用
    for rid in ("R-1", "R-2"):
        if rid not in rule_ids:
            errors.append(f"8.0 登记表缺少翻新线规则 {rid} 行（id 不回收，翻新线卡点同样要登记）")
            continue
        for label, sec_pat, text in (
            ("步骤定义 §3.4", r"^### 3\.4 .*?(?=^## |^### )", stepdef_text),
            ("卡点协议 人工卡点表", r"^## 一、.*?(?=^## 二、|^### )", gates_text),
        ):
            sec = re.search(sec_pat, text, re.M | re.S)
            if not sec:
                errors.append(f"{label} 章节解析失败")
            elif rid not in sec.group(0):
                errors.append(f"{label} 未引用翻新线卡点 {rid}（8.0 登记后必须在协议/卡点章节有落点）")

    if rule_ids:
        text_cache = {
            ROOT_MARKER: main_text,
            STEPDEF_FILE: stepdef_text,
            RULEBOOK_FILE: rulebook_text,
            GATE_FILE: gates_text,
            EXEC_FILE: exec_text,
        }
        probe_files = [
            root / ROOT_MARKER, root / STEPDEF_FILE, root / RULEBOOK_FILE,
            root / GATE_FILE, root / EXEC_FILE, root / "workflow" / "steps.yaml",
        ]
        probe_files += sorted((root / "prompts").glob("*.md"))
        probe_files += sorted((root / "scripts").glob("*.py"))
        for f in probe_files:
            if not f.exists():
                continue
            text = text_cache.get(f.name)
            if text is None:
                text = f.read_text(encoding="utf-8", errors="ignore")
            refs = {"R" + m.group(1) for m in RULE_REF_RE.finditer(text)}
            for m in RULE_RANGE_RE.finditer(text):
                a, b = int(m.group(1)), int(m.group(2))
                if 0 < a <= b and b - a <= 1000:
                    refs.update(f"R{i}" for i in range(a, b + 1))
            unknown = sorted(r for r in refs if r not in rule_ids)
            if unknown:
                try:
                    rel = f.relative_to(root)
                except ValueError:
                    rel = f
                errors.append(
                    f"{rel} 引用了 8.0 未登记的规则 {', '.join(unknown)}"
                    "（新增规则必须先补登记表再引用）"
                )

    # 主控「总执行顺序」流程图必须覆盖全部步骤 id（防止步骤表改了流程图没改）
    sec0 = re.search(r"^## 总执行顺序.*?(?=^## )", main_text, re.M | re.S)
    if not sec0:
        errors.append("总执行顺序流程图解析失败（找不到主控「## 总执行顺序」章节）")
    else:
        s0 = sec0.group(0)
        for sid in sorted(id_set | design_ids):
            if not re.search(r"(?<![\w.])" + re.escape(sid) + r"(?![\w.])", s0):
                errors.append(f"总执行顺序流程图缺少步骤 {sid}（步骤定义表与流程图须同步）")

    # 并发闸门脚本兜底：多个进行中项目时，每个的看板当前步骤必须明确
    queue_file = root / QUEUE_FILE
    if queue_file.exists():
        queue_text = queue_file.read_text(encoding="utf-8")
        active_projects = []
        for line in queue_text.splitlines():
            if not line.strip().startswith("|"):
                continue
            cells = [c.strip() for c in line.split("|")[1:-1]]
            if len(cells) != 9:
                continue
            name = cells[0].strip()
            state = cells[4].strip()
            if not name or name == "项目名" or set(name) <= set("-: "):
                continue
            if state.startswith("进行中"):
                active_projects.append(name)
        if len(active_projects) > 1:
            for pname in active_projects:
                pdir = root / "projects" / pname
                if pdir.exists():
                    b = _read_board(pdir)
                    if not b["stage"] or "未开始" in b["stage"]:
                        errors.append(f"并发项目 {pname}: 看板「当前阶段」为空或「未开始」，并发必须明确当前步骤")

    board_text = (root / "projects" / TEMPLATE_NAME / "_项目状态.md").read_text(encoding="utf-8")
    gate_count = sum(len(s.get("artifacts") or []) for s in steps)
    for sid in ids:
        if f"| {sid} |" not in board_text:
            errors.append(f"{sid}: 看板模板缺少该步骤行")
        if f"| {sid} |" not in stepdef_text:
            errors.append(f"{sid}: WORKFLOW_步骤定义.md 步骤表缺少该步骤行")

    if errors:
        print(f"🔴 steps.yaml 一致性校验失败（{len(errors)} 项）：")
        for e in errors:
            print(f"   - {e}")
        sys.exit(1)

    total_steps = len(id_set | design_ids)
    print(
        f"🟢 steps.yaml 一致：{total_steps} 个步骤 / {len(rule_ids)} 条规则 · {gate_count} 项门禁产物 · "
        "提示词/看板模板/步骤定义/规则库/卡点协议/流程图/规则引用全部对上"
    )


# ---------- 子命令 ----------

def cmd_init(args):
    root = find_root()
    tpl = root / "projects" / TEMPLATE_NAME
    dst = root / "projects" / args.name
    if dst.exists():
        print(f"❌ 项目已存在：{dst}")
        sys.exit(1)
    shutil.copytree(tpl, dst)

    desc = args.desc or ""
    if args.desc_file:
        desc = Path(args.desc_file).read_text(encoding="utf-8")
    if desc:
        (dst / "00_原始项目描述.md").write_text(f"# 原始项目描述 · {args.name}\n\n{desc}\n", encoding="utf-8")

    # 更新看板基本信息
    board = dst / "_项目状态.md"
    text = board.read_text(encoding="utf-8")
    text = text.replace("项目名：<项目名>", f"项目名：{args.name}")
    text = text.replace("创建日期：<YYYY-MM-DD>", f"创建日期：{datetime.date.today().isoformat()}")
    board.write_text(text, encoding="utf-8")

    print(f"✅ 项目已创建：{dst}")
    print(f"   下一步：把原始描述发给 AI，或直接运行 wf prompt 1 获取第 1 步提示词")


def cmd_list(_args):
    root = find_root()
    for p in sorted((root / "projects").iterdir()):
        if p.is_dir() and p.name != TEMPLATE_NAME:
            board = p / "_项目状态.md"
            stage = ""
            if board.exists():
                m = re.search(r"当前阶段：\*\*(.+?)\*\*", board.read_text(encoding="utf-8"))
                stage = m.group(1) if m else ""
            print(f"  📁 {p.name}  —  {stage}")


def cmd_status(args):
    root = find_root()
    board = project_dir(root, args.name) / "_项目状态.md"
    print(board.read_text(encoding="utf-8"))


def cmd_next(args):
    root = find_root()
    board = project_dir(root, args.name) / "_项目状态.md"
    text = board.read_text(encoding="utf-8")
    m = re.search(r"当前阶段：\*\*(.+?)\*\*", text)
    stage = m.group(1) if m else "未知"
    print(f"当前阶段：{stage}\n")

    m2 = re.search(r"第\s*([\d.]+[AB]?)\s*步", stage)
    if m2:
        step = m2.group(1)
        prompt = step_to_prompt(root, step)
        print(f"应使用的提示词模板：{prompt.relative_to(root)}")
        print("=" * 50)
        print(prompt.read_text(encoding="utf-8"))

    # 提示卡点
    block = re.search(r"## 当前卡点（需要用户做什么）\n\n(.*?)\n\n## ", text, re.DOTALL)
    if block and "无" not in block.group(1).strip()[:4]:
        print("=" * 50)
        print("⚠️ 当前卡点：")
        print(block.group(1).strip())


def cmd_prompt(args):
    root = find_root()
    prompt = step_to_prompt(root, args.step)
    print(prompt.read_text(encoding="utf-8"))


def cmd_advance(args):
    root = find_root()
    board = project_dir(root, args.name) / "_项目状态.md"
    text = board.read_text(encoding="utf-8")
    text = re.sub(r"- 当前阶段：\*\*.+?\*\*", f"- 当前阶段：**{args.stage}**", text)
    board.write_text(text, encoding="utf-8")
    print(f"✅ 看板已更新：当前阶段 = {args.stage}")


def cmd_log(args):
    root = find_root()
    script = root / "scripts" / "log_failure.py"
    cmd = [sys.executable, str(script), str(project_dir(root, args.name)),
           "--step", args.step, "--category", args.category,
           "--desc", args.desc, "--ai-error", args.ai_error or "",
           "--human-catch", args.human_catch or "",
           "--rounds", args.rounds, "--root-cause", args.root_cause]
    sys.exit(subprocess.call(cmd))


def cmd_check(args):
    root = find_root()
    scripts = root / "scripts"
    if args.kind == "contract":
        v = scripts / "api_contract_validator.py"
        if args.action == "export":
            cmd = [sys.executable, str(v), "export", args.url, args.out]
        else:
            cmd = [sys.executable, str(v), "check", args.openapi, args.frontend]
        sys.exit(subprocess.call(cmd))
    path = getattr(args, "path", ".")
    script = {
        "deps": "dependency_checker.py",
        "secrets": "security_scan_secrets.py",
        "regression": "p0_regression_test.py",
    }[args.kind]
    sys.exit(subprocess.call([sys.executable, str(scripts / script), path]))


# ---------- 入口 ----------

def main():
    # 中文 Windows 默认 cp936：emoji/中文输出会 UnicodeEncodeError（改进项）。
    # 入口统一把标准输出/错误切 UTF-8（errors=replace 兜底），不支持 reconfigure 的流跳过。
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (AttributeError, ValueError, OSError):
                pass

    ap = argparse.ArgumentParser(prog="wf", description="从 0 到 1 项目自动工作流 CLI")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init", help="从模板创建新项目")
    p.add_argument("name")
    p.add_argument("--desc", default="")
    p.add_argument("--desc-file", default="")
    p.set_defaults(fn=cmd_init)

    p = sub.add_parser("list", help="列出所有项目")
    p.set_defaults(fn=cmd_list)

    p = sub.add_parser("status", help="查看项目进度看板")
    p.add_argument("name")
    p.set_defaults(fn=cmd_status)

    p = sub.add_parser("next", help="当前步骤 + 应使用的提示词模板")
    p.add_argument("name")
    p.set_defaults(fn=cmd_next)

    p = sub.add_parser("prompt", help="打印指定步骤的提示词模板")
    p.add_argument("step")
    p.set_defaults(fn=cmd_prompt)

    p = sub.add_parser("advance", help="更新看板当前阶段")
    p.add_argument("name")
    p.add_argument("stage")
    p.set_defaults(fn=cmd_advance)

    p = sub.add_parser("queue", help="队列事实列：从看板/门禁推导")
    p.add_argument("--sync", action="store_true", help="把推导结果回写队列文件")
    p.add_argument("--check", action="store_true", help="只校验，不一致退出码 1")
    p.add_argument("--allow-missing", action="store_true",
                   help="CI 用：projects/ 下目录不存在的队列行跳过比对并汇总提示，不算失败")
    p.set_defaults(fn=cmd_queue)

    p = sub.add_parser("steps", help="列出/校验 workflow/steps.yaml")
    p.add_argument("--check", action="store_true", help="校验提示词/fallback/看板/主控是否对得上")
    p.set_defaults(fn=cmd_steps)

    p = sub.add_parser("log", help="记录失败日志")
    p.add_argument("name")
    p.add_argument("--step", required=True)
    p.add_argument("--category", required=True,
                   choices=["AI产出错误", "真实运行报错", "回归未通过", "人工卡点拦截", "评审打回", "验收不通过"])
    p.add_argument("--desc", required=True)
    p.add_argument("--ai-error", default="")
    p.add_argument("--human-catch", default="")
    p.add_argument("--rounds", default="1")
    p.add_argument("--root-cause", default="其他",
                   choices=["幻觉依赖/版本", "跨文件不一致", "沉默的缺失", "逻辑错误", "需求理解偏差", "上下文遗忘", "安全问题", "环境/配置", "其他"])
    p.set_defaults(fn=cmd_log)

    # 独立子解析器：契约校验的文档写法是 `wf check contract export <url> <out>` /
    # `wf check contract check <openapi> <frontend>`，参数位不能再用 path/action/a/b 平铺（会错位成 TypeError）
    p = sub.add_parser("check", help="机器校验（deps/secrets/contract/regression）")
    check_sub = p.add_subparsers(dest="kind", required=True)
    for kind, kind_help in (
        ("deps", "依赖版本真实性校验"),
        ("secrets", "硬编码密钥扫描"),
        ("regression", "P0 自动化回归测试"),
    ):
        kp = check_sub.add_parser(kind, help=kind_help)
        kp.add_argument("path", nargs="?", default=".")
        kp.set_defaults(fn=cmd_check)
    p_contract = check_sub.add_parser("contract", help="接口契约：导出 OpenAPI / 校验前端调用")
    contract_sub = p_contract.add_subparsers(dest="action", required=True)
    pe = contract_sub.add_parser("export", help="导出后端 OpenAPI 契约")
    pe.add_argument("url")
    pe.add_argument("out")
    pe.set_defaults(fn=cmd_check)
    pc = contract_sub.add_parser("check", help="校验前端调用符合契约")
    pc.add_argument("openapi")
    pc.add_argument("frontend")
    pc.set_defaults(fn=cmd_check)

    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
