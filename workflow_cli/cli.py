#!/usr/bin/env python3
"""
wf — 从 0 到 1 项目自动工作流命令行工具

命令：
  wf init <项目名> [--desc "原始描述" | --desc-file 路径]   从模板创建新项目
  wf list                                                    列出所有项目
  wf status [项目名]                                          查看项目进度看板
  wf next [项目名]                                            当前步骤 + 应使用的提示词模板
  wf prompt <步骤号>                                          打印指定步骤的提示词模板（如 wf prompt 6 / wf prompt 8.5）
  wf advance <项目名> <阶段描述>                              更新看板「当前阶段」
  wf queue [--sync | --check]                                 队列事实列：从看板+门禁推导 / 回写 / 校验
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


def step_to_prompt(root: Path, step: str) -> Path:
    """步骤号 -> prompts/ 下的模板文件（优先读 steps.yaml，未登记时按命名兜底）"""
    for s in _load_steps(root):
        if str(s["id"]).upper() == step.upper():
            if not s.get("prompt"):
                print(f"第 {step} 步（{s['name']}）无提示词模板，按主控 §2 用脚本/命令执行。")
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
    current_state 为队列行现有状态；若为「已搁置」且项目无生产目录，保留已搁置不覆盖。"""
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

    artifacts_ok = all(gate.check_one(pdir, it)["status"] == "OK" for it in gate.GATE_ITEMS)
    board_status = gate.check_board_consistency(pdir)["status"]

    date = b["dates"][0] if b["dates"] else None
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


def cmd_queue(args):
    root = find_root()
    gate = _load_gate_module(root)
    path, lines, rows = _queue_rows(root)
    diffs = []
    for idx, cells in rows:
        name = cells[0].strip()
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
            sys.exit(0)
        print("🔴 队列事实列已过期（状态/完成日期/当前卡点禁止手改）：")
        for name, changed in diffs:
            for field, old, new in changed:
                print(f"   - {name} · {field}：表里是「{old}」，推导应为「{new}」")
        print("   → 运行 wf queue --sync 回写")
        sys.exit(1)

    if args.sync:
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"✅ 队列已回写：{path.name}（事实列 {len(diffs)} 处更新）")
        for name, changed in diffs:
            print(f"   - {name}：" + "；".join(f"{f}: {o} → {n}" for f, o, n in changed))
        return

    for name, changed in diffs:
        print(f"  {name}：" + "；".join(f"{f}: {o} → {n}" for f, o, n in changed))
    print(f"\n共 {len(diffs)} 个项目的事实列与看板不一致。运行 wf queue --sync 回写，或 --check 用于 CI。")


def cmd_steps(args):
    """列出 / 校验 steps.yaml：提示词、fallback、看板模板与主控 §2 是否对得上。"""
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
    ids = [str(s["id"]) for s in steps]
    if len(ids) != len(set(ids)):
        errors.append("步骤 id 重复")
    id_set = set(ids)
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

    # §8.0 登记表 vs 规则实体（正文活跃 ∪ 休眠区）一致。
    # 关键：休眠不是删除——规则休眠后从正文移入休眠区（标题变为 "R<id> …（休眠于…）"），
    # 登记表行必须保留（id 不回收）。三方 id 集合必须相等，缺一报红。
    main_text = (root / ROOT_MARKER).read_text(encoding="utf-8")
    table_ids = set(re.findall(r"^\| R(\d+) \|", main_text, re.M))
    section8 = re.search(r"^## 8\. .*?^## 9\. ", main_text, re.M | re.S)
    body_ids, dormant_ids = set(), set()
    if section8:
        s8 = section8.group(0)
        # 正文活跃规则标题 "N. **"，不含休眠区（休眠区条目是 "R<id> …" 格式，不会误匹配）
        body_ids = set(re.findall(r"^(\d+)\. \*\*", s8, re.M))
        dormant_block = re.search(r"^### 休眠规则.*", s8, re.M | re.S)
        if dormant_block:
            for line in dormant_block.group(0).splitlines():
                if line.strip().startswith(">"):  # 跳过说明性引用行
                    continue
                dormant_ids.update(re.findall(r"\bR(\d+)\b", line))
    entity_ids = body_ids | dormant_ids
    if not table_ids or not section8:
        errors.append("§8.0 登记表或 §8 章节解析失败")
    elif table_ids != entity_ids:
        only_table = sorted(table_ids - entity_ids, key=int)
        only_entity = sorted(entity_ids - table_ids, key=int)
        if only_table:
            errors.append(
                f"§8.0 登记表有 R{','.join(only_table)} 但正文和休眠区都没有"
                "（id 不回收：要么移回正文，要么移入休眠区，不许只删正文）"
            )
        if only_entity:
            errors.append(
                f"正文/休眠区有 R{','.join(only_entity)} 但 §8.0 登记表缺行"
                "（新增/休眠规则必须先补登记表）"
            )

    # §0 流程图必须覆盖 steps.yaml 全部步骤 id（防止步骤表改了流程图没改）
    sec0 = re.search(r"^## 0\. .*?^## 1\. ", main_text, re.M | re.S)
    if not sec0:
        errors.append("§0 章节解析失败")
    else:
        s0 = sec0.group(0)
        for sid in ids:
            if not re.search(r"(?<![\w.])" + re.escape(sid) + r"(?![\w.])", s0):
                errors.append(f"§0 流程图缺少步骤 {sid}（§2 步骤表与 §0 流程图须同步）")

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
    main_text = (root / ROOT_MARKER).read_text(encoding="utf-8")
    gate_count = sum(len(s.get("artifacts") or []) for s in steps)
    for sid in ids:
        if f"| {sid} |" not in board_text:
            errors.append(f"{sid}: 看板模板缺少该步骤行")
        if f"| {sid} |" not in main_text:
            errors.append(f"{sid}: 主控 §2 缺少该步骤行")

    if errors:
        print(f"🔴 steps.yaml 一致性校验失败（{len(errors)} 项）：")
        for e in errors:
            print(f"   - {e}")
        sys.exit(1)

    print(f"🟢 steps.yaml 一致：{len(ids)} 个步骤 · {gate_count} 项门禁产物 · 提示词/看板模板/主控 §2 全部对上")


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
    if args.kind == "deps":
        sys.exit(subprocess.call([sys.executable, str(scripts / "dependency_checker.py"), args.path]))
    elif args.kind == "secrets":
        sys.exit(subprocess.call([sys.executable, str(scripts / "security_scan_secrets.py"), args.path]))
    elif args.kind == "regression":
        sys.exit(subprocess.call([sys.executable, str(scripts / "p0_regression_test.py"), args.path]))
    elif args.kind == "contract":
        v = scripts / "api_contract_validator.py"
        if args.action == "export":
            sys.exit(subprocess.call([sys.executable, str(v), "export", args.a, args.b]))
        else:
            sys.exit(subprocess.call([sys.executable, str(v), "check", args.a, args.b]))


# ---------- 入口 ----------

def main():
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

    p = sub.add_parser("check", help="机器校验（deps/secrets/contract/regression）")
    p.add_argument("kind", choices=["deps", "secrets", "contract", "regression"])
    p.add_argument("path", nargs="?", default=".")
    p.add_argument("action", nargs="?")
    p.add_argument("a", nargs="?")
    p.add_argument("b", nargs="?")
    p.set_defaults(fn=cmd_check)

    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
