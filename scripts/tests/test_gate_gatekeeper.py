#!/usr/bin/env python3
"""观察期自动转硬闸机制单测（G1/G8 · gate_gatekeeper + _gate_states）。

运行：python -m pytest scripts/tests -q
覆盖：
  - 缺省 observe 旁路；无误报达阈值自动翻 strict；误报清零保持 observe；review 幂等不重复计数
  - mark-fp 标记最近一条观察记录；观察日志读写 / counted 标记
"""

import argparse
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import _gate_states as gates  # noqa: E402
import gate_gatekeeper as gg  # noqa: E402


def _initial_states(threshold: int = 1) -> dict:
    gate = {
        "display": "测试闸",
        "status": "observe",
        "threshold_projects": threshold,
        "observed_projects": 0,
        "false_positives": 0,
        "since": "2026-11-11",
        "activated_at": None,
        "activated_project": None,
    }
    return {"gates": {"input_card": dict(gate), "criterion_mapping": dict(gate)}}


def _setup(tmp_path, monkeypatch, threshold: int = 1):
    sp = tmp_path / "gate_states.yaml"
    sp.write_text(
        yaml.safe_dump(_initial_states(threshold), allow_unicode=True),
        encoding="utf-8",
    )
    monkeypatch.setattr(gates, "GATE_STATES_PATH", sp)
    monkeypatch.setattr(gg, "gates", gates)  # gg 内 `import _gate_states as gates`
    proj = tmp_path / "proj"
    proj.mkdir()
    return proj, sp


def _review(proj: Path) -> int:
    return gg.cmd_review(argparse.Namespace(project_dir=str(proj)))


def test_default_observe_not_strict(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    assert gates.is_strict("input_card") is False
    assert gates.is_strict("criterion_mapping") is False


def test_review_promotes_on_clean_project(tmp_path, monkeypatch):
    proj, sp = _setup(tmp_path, monkeypatch)
    gates.record_observation(proj, "input_card", 0, False, "clean")

    rc = _review(proj)
    assert rc == 0

    states = gates.load_states()
    g = states["gates"]["input_card"]
    assert g["status"] == "strict"
    assert g["observed_projects"] == 1
    assert g["activated_project"] == proj.name
    assert g["activated_at"]  # 已记激活日期


def test_review_resets_on_false_positive(tmp_path, monkeypatch):
    proj, sp = _setup(tmp_path, monkeypatch)
    gates.record_observation(proj, "input_card", 2, False, "first")
    gates.mark_fp(proj, "input_card", "路径含括号被误判越界")

    rc = _review(proj)
    assert rc == 0

    g = gates.load_states()["gates"]["input_card"]
    assert g["status"] == "observe"
    assert g["observed_projects"] == 0
    assert g["false_positives"] == 1


def test_review_is_idempotent(tmp_path, monkeypatch):
    # threshold=2：第一次 review 计 1，第二次无新观察行不得重复 +1
    proj, sp = _setup(tmp_path, monkeypatch, threshold=2)
    gates.record_observation(proj, "input_card", 0, False, "clean")

    _review(proj)
    first = gates.load_states()["gates"]["input_card"]["observed_projects"]
    _review(proj)
    second = gates.load_states()["gates"]["input_card"]["observed_projects"]

    assert first == 1
    assert second == 1
    assert gates.load_states()["gates"]["input_card"]["status"] == "observe"


def test_mark_fp_flags_latest_record(tmp_path, monkeypatch):
    proj, _ = _setup(tmp_path, monkeypatch)
    gates.record_observation(proj, "input_card", 1, False, "old")
    gates.record_observation(proj, "input_card", 1, False, "new")

    assert gates.mark_fp(proj, "input_card", "误报") is True
    rows = gates.read_observations(proj, "input_card")
    assert rows[0]["false_positive"] is False
    assert rows[1]["false_positive"] is True
    assert rows[1]["note"] == "误报"


def test_review_skips_gate_without_observation(tmp_path, monkeypatch):
    proj, _ = _setup(tmp_path, monkeypatch)
    # 本项目只跑过 input_card，criterion_mapping 无观察日志 → 不计入、不误转
    gates.record_observation(proj, "input_card", 0, False, "clean")
    _review(proj)
    cm = gates.load_states()["gates"]["criterion_mapping"]
    assert cm["status"] == "observe"
    assert cm["observed_projects"] == 0


def test_missing_state_file_stays_bypass(tmp_path, monkeypatch):
    # 状态文件读不到 → 保守旁路，不误判 strict
    monkeypatch.setattr(gates, "GATE_STATES_PATH", tmp_path / "nope.yaml")
    assert gates.is_strict("input_card") is False
