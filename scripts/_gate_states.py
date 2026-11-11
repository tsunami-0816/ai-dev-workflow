#!/usr/bin/env python3
"""
新闸观察期状态共享模块（G1/G8 · 2026-11-11）

状态文件：`workflow/gate_states.yaml`（机器维护，见文件头注释）。
项目观察日志：`<项目根>/.gate_observations/<gate>.jsonl`，每行一条 JSON。

保守原则：状态文件读不到 / 解析失败 / 缺 PyYAML 时，一律按 observe 旁路处理，
不误阻塞现有流水线（对应 R12：脚本自身会错，先怀疑脚本）。
"""

import datetime
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GATE_STATES_PATH = ROOT / "workflow" / "gate_states.yaml"
OBS_DIR = ".gate_observations"

try:
    import yaml  # type: ignore
    _HAS_YAML = True
except Exception:
    yaml = None
    _HAS_YAML = False

_STATE_HEADER = """# 新闸观察期状态（方案 §8：连续 threshold_projects 个项目无误报后，由 gate_gatekeeper.py 自动转阻塞硬闸）
#
# status 口径：observe = 旁路观察期（警告不阻塞）；strict = 阻塞硬闸（不绿即 exit 1）。
# 自动转闸判据：本项目该闸无误报 → observed_projects +1；达阈值翻 strict；有误报则清零继续 observe。
# 本文件 observed_projects / false_positives / activated_* 由脚本自动维护，不要手改。
# 读不到本文件或解析失败时，保守按 observe 旁路处理（R12：先怀疑脚本，不误阻塞）。

"""


def today_str() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d")


def load_states() -> dict:
    """读 gate_states.yaml；任何异常返回空 dict（调用方按缺省 observe 处理）。"""
    if not _HAS_YAML or not GATE_STATES_PATH.exists():
        return {}
    try:
        data = yaml.safe_load(GATE_STATES_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def get_gate(name: str) -> dict:
    return load_states().get("gates", {}).get(name, {}) or {}


def is_strict(name: str) -> bool:
    """该闸当前是否阻塞硬闸；缺省/异常均为 False（旁路）。"""
    return get_gate(name).get("status") == "strict"


def save_states(states: dict) -> None:
    """写回状态文件，保留文件头注释。"""
    if not _HAS_YAML:
        raise RuntimeError("缺 PyYAML，无法写回 gate_states.yaml")
    text = _STATE_HEADER + yaml.safe_dump(
        states, allow_unicode=True, sort_keys=False, default_flow_style=False
    )
    GATE_STATES_PATH.write_text(text, encoding="utf-8")


def _obs_path(project_dir: Path, gate: str) -> Path:
    return Path(project_dir) / OBS_DIR / f"{gate}.jsonl"


def record_observation(project_dir, gate: str, issues: int,
                        false_positive: bool = False, note: str = "") -> None:
    """追加一条观察记录到项目日志；项目目录为空则跳过。"""
    if not project_dir:
        return
    path = _obs_path(Path(project_dir), gate)
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "ts": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "gate": gate,
        "issues": int(issues or 0),
        "false_positive": bool(false_positive),
        "note": note or "",
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_observations(project_dir, gate: str) -> list[dict]:
    """读项目某闸观察日志；坏行跳过。文件不存在返回空列表。"""
    path = _obs_path(Path(project_dir), gate)
    if not path.exists():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return rows


def _write_rows(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def mark_fp(project_dir, gate: str, note: str = "") -> bool:
    """把该闸最近一条未标记的观察记录标为误报（R12 人工确认脚本误判时用）。"""
    path = _obs_path(Path(project_dir), gate)
    rows = read_observations(project_dir, gate)
    target = None
    for r in reversed(rows):
        if not r.get("false_positive"):
            target = r
            break
    if target is None:
        return False
    target["false_positive"] = True
    if note:
        target["note"] = note
    _write_rows(path, rows)
    return True


def mark_counted(project_dir, gate: str, timestamps: set[str]) -> None:
    """review 计入过的观察行打 counted 标记，避免同一项目重复计数（幂等）。"""
    path = _obs_path(Path(project_dir), gate)
    rows = read_observations(project_dir, gate)
    for r in rows:
        if r.get("ts") in timestamps:
            r["counted"] = True
    _write_rows(path, rows)
