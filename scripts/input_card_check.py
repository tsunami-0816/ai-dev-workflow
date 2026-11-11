#!/usr/bin/env python3
"""
输入卡 Schema 校验（G1 · 2026-11-11；配套 G2 范围/限额校验）

专治「步骤交接卡缺字段、引用的上游产物不存在、路径越出项目目录、枚举值写错」：
接收方开工前先 validate，非法直接拒绝，不做「解释执行」（typed handoff）。

用法：
  python scripts/input_card_check.py <step> <card.yaml> --project <项目目录>
  python scripts/input_card_check.py 5A 05_代码/backend/input_card.yaml --project projects/xxx

旁路口径（方案 §8）：闸口状态由 `workflow/gate_states.yaml` 驱动——observe 观察期校验不绿
先 ⚠️ 警告、exit 0；连续一个项目无误报后由 `gate_gatekeeper.py` 自动翻 strict 硬闸（exit 1）。
`--strict` 仅作临时强制阻塞，不改状态文件。历史项目豁免。

校验规则（定义见 workflow/input_card_schema.yaml）：
  - 通用必填：step / project / updated_at / sources
  - sources 引用路径必须落在项目目录内；传 --project 时再校验产物真实存在
  - 分步骤扩展必填字段（step_specific）
  - tasks 列表项必填 task_id/desc；risk 枚举 低/中/高/关键
  - G2：scope.files_in_scope 与 out_of_scope 不得相交；limits 字段为正整数
  - ports 为 dict，值为 1-65535 端口号

退出码：0 = 全绿；1 = 报红（缺失/越界/失效引用/枚举非法/自相矛盾，逐条列出）；
        2 = 脚本自身错误（缺 PyYAML / 文件读不到 / schema 损坏；按 R12 先怀疑脚本）。
历史项目豁免：门禁上线前创建的项目可不跑本闸，不追溯。
"""

import argparse
import fnmatch
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - 环境缺依赖时给出明确退出码 2
    yaml = None

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCHEMA = ROOT / "workflow" / "input_card_schema.yaml"

import _gate_states as gates  # noqa: E402

DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}( \d{2}:\d{2})?$")
PORT_PATTERN = re.compile(r"^\d+$")


def _force_utf8_output():
    """Windows 默认 cp936/GBK 控制台下打印中文/emoji 会 UnicodeEncodeError；入口处统一切 UTF-8。"""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def _load_schema(path: Path) -> dict:
    if not path.exists():
        raise ValueError(f"Schema 文件不存在：{path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Schema 文件不是合法 YAML 映射")
    return data


def _is_relative_within_project(p: str) -> bool:
    """路径不许是绝对路径（盘符/UNC），也不许用 .. 越出项目根。"""
    if not p or p.strip() == "":
        return False
    pp = Path(p)
    if pp.is_absolute():
        return False
    # 规范化后仍含 .. 视为越界
    parts = pp.parts
    if ".." in parts:
        return False
    return True


def _resolve_within(root: Path, rel: str) -> Path | None:
    """把相对路径拼到项目根；越出根目录返回 None。"""
    candidate = (root / rel).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        return None
    return candidate


def _scope_disjoint(in_scope: list, out_of_scope: list) -> list[str]:
    """返回相交的冲突对（glob 简化匹配）。"""
    conflicts = []
    for out in out_of_scope or []:
        for inc in in_scope or []:
            if fnmatch.fnmatch(inc, out) or fnmatch.fnmatch(out, inc) or inc == out:
                conflicts.append(f"{inc} ↔ 排除项 {out}")
    return conflicts


def check_card(step: str, card: dict, schema: dict, project: Path | None) -> list[str]:
    errors: list[str] = []
    common = schema.get("common", {})
    fields = common.get("fields", {})

    # ---- 通用必填 ----
    for key in common.get("required", []):
        value = card.get(key)
        if value is None or (isinstance(value, str) and not value.strip()):
            errors.append(f"缺必填字段：{key}")

    # ---- step 枚举 + 与命令行一致 ----
    card_step = str(card.get("step", "")).strip()
    step_enum = fields.get("step", {}).get("enum", [])
    if card_step and card_step not in step_enum:
        errors.append(f"step 枚举非法：{card_step!r}（允许：{', '.join(step_enum)}）")
    if card_step and step and card_step != step:
        errors.append(f"卡内 step={card_step!r} 与命令行 step={step!r} 不一致")

    # ---- updated_at 格式 ----
    updated = str(card.get("updated_at", "") or "")
    if updated and not DATE_PATTERN.match(updated):
        errors.append("updated_at 格式应为 YYYY-MM-DD 或 YYYY-MM-DD HH:MM")

    # ---- sources 引用路径 ----
    sources = card.get("sources")
    if sources is not None:
        if not isinstance(sources, list) or not sources:
            errors.append("sources 必须是非空列表（上游产物引用路径）")
        else:
            for rel in sources:
                rel_s = str(rel).strip()
                if not _is_relative_within_project(rel_s):
                    errors.append(f"sources 路径越出项目目录或为绝对路径：{rel_s!r}")
                    continue
                if project is not None:
                    resolved = _resolve_within(project, rel_s)
                    if resolved is None:
                        errors.append(f"sources 路径越出项目目录：{rel_s!r}")
                    elif not resolved.exists():
                        errors.append(f"sources 引用的上游产物不存在：{rel_s!r}")

    # ---- 分步骤扩展必填 ----
    step_specific = schema.get("step_specific", {})
    spec = step_specific.get(card_step) or step_specific.get(step)
    if spec:
        for key in spec.get("required", []):
            value = card.get(key)
            if value is None or (isinstance(value, str) and not value.strip()) \
                    or (isinstance(value, (list, dict)) and not value):
                errors.append(f"step {card_step} 缺必填字段：{key}")

    # ---- tasks 列表项 ----
    tasks = card.get("tasks")
    if tasks is not None:
        if not isinstance(tasks, list):
            errors.append("tasks 必须是列表")
        else:
            task_req = schema.get("task_item", {}).get("required", [])
            risk_enum = schema.get("task_item", {}).get("risk_enum", [])
            for i, task in enumerate(tasks, 1):
                if not isinstance(task, dict):
                    errors.append(f"tasks[{i}] 不是映射对象")
                    continue
                for key in task_req:
                    if not str(task.get(key, "") or "").strip():
                        errors.append(f"tasks[{i}] 缺字段：{key}")
                risk = str(task.get("risk", "") or "").strip()
                if risk and risk not in risk_enum:
                    errors.append(f"tasks[{i}] risk 枚举非法：{risk!r}（允许：{', '.join(risk_enum)}）")

    # ---- G2 scope ----
    scope = card.get("scope")
    if scope is not None:
        if not isinstance(scope, dict):
            errors.append("scope 必须是映射 {files_in_scope, out_of_scope}")
        else:
            in_scope = scope.get("files_in_scope") or []
            out_scope = scope.get("out_of_scope") or []
            if not isinstance(in_scope, list) or not isinstance(out_scope, list):
                errors.append("scope.files_in_scope / out_of_scope 必须是列表")
            else:
                conflicts = _scope_disjoint(in_scope, out_scope)
                for c in conflicts:
                    errors.append(f"scope 自相矛盾（排除项命中了范围项）：{c}")

    # ---- G2 limits ----
    limits = card.get("limits")
    if limits is not None:
        if not isinstance(limits, dict):
            errors.append("limits 必须是映射 {max_files, max_attempts, timeout_min}")
        else:
            for key, val in limits.items():
                if isinstance(val, bool) or not isinstance(val, int) or val <= 0:
                    errors.append(f"limits.{key} 必须是正整数，收到：{val!r}")

    # ---- ports ----
    ports = card.get("ports")
    if ports is not None:
        if not isinstance(ports, dict):
            errors.append("ports 必须是 dict（如 backend: 8083）")
        else:
            for name, val in ports.items():
                sval = str(val).strip()
                if not PORT_PATTERN.match(sval) or not (1 <= int(sval) <= 65535):
                    errors.append(f"ports.{name} 不是合法端口号：{val!r}")

    return errors


def main():
    ap = argparse.ArgumentParser(description="输入卡 Schema 校验（G1）")
    ap.add_argument("step", help="步骤编号，如 5A / 6 / 8")
    ap.add_argument("card", help="输入卡 YAML 路径")
    ap.add_argument("--project", help="项目目录（提供后校验 sources 产物真实存在、路径不越界）")
    ap.add_argument("--schema", default=str(DEFAULT_SCHEMA), help="Schema YAML 路径（一般不用改）")
    ap.add_argument("--strict", action="store_true",
                    help="转阻塞闸：有错误即 exit 1；缺省为旁路观察期，仅警告 exit 0")
    args = ap.parse_args()

    if yaml is None:
        print("❌ 缺 PyYAML 依赖：pip install pyyaml（或 pip install -e \".[test]\"）", file=sys.stderr)
        sys.exit(2)

    card_path = Path(args.card)
    if not card_path.exists():
        print(f"❌ 输入卡文件不存在：{card_path}", file=sys.stderr)
        sys.exit(2)

    try:
        schema = _load_schema(Path(args.schema))
        card = yaml.safe_load(card_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, yaml.YAMLError) as e:
        print(f"❌ 读取/解析失败（脚本或文件问题，按 R12 先怀疑脚本）：{e}", file=sys.stderr)
        sys.exit(2)

    if not isinstance(card, dict):
        print("❌ 输入卡不是合法 YAML 映射（应为 step/project/... 字段）")
        sys.exit(1)

    project = Path(args.project).resolve() if args.project else None
    if project is not None and not project.is_dir():
        print(f"❌ --project 目录不存在：{project}", file=sys.stderr)
        sys.exit(2)

    errors = check_card(args.step.strip(), card, schema, project)
    strict = args.strict or gates.is_strict("input_card")

    if errors:
        if not strict:
            # 旁路观察期：记一条观察日志，供 gate_gatekeeper review 判定转闸
            gates.record_observation(project, "input_card", len(errors))
        if strict:
            print(f"🔴 输入卡校验不通过：{card_path.name}（step {args.step}），共 {len(errors)} 条：")
            for e in errors:
                print(f"   - {e}")
            print("   补卡后重跑本校验；卡不绿不得动手开发（历史项目豁免）。")
            sys.exit(1)
        # 旁路观察期：警告但不阻塞
        print(f"⚠️ 输入卡有 {len(errors)} 条待核（旁路观察期，未阻塞）：")
        for e in errors:
            print(f"   - {e}")
        print("   观察期内先记录、不挡开工；连续一个项目无误报后由 gate_gatekeeper 自动转阻塞闸。")
        sys.exit(0)

    print(f"✅ 输入卡校验通过：{card_path.name}（step {args.step}）")
    sys.exit(0)


if __name__ == "__main__":
    _force_utf8_output()
    main()
