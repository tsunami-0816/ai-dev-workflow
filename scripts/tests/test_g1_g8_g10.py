#!/usr/bin/env python3
"""G1 输入卡校验 / G8 指标挂接 / G10 断点脚本的最小 fixture 自测。

运行：python -m pytest scripts/tests -q
覆盖：
  - input_card_check.py：合法卡全绿；越界路径 / scope 相交 / limits 非正整数 / risk 非法枚举 报红
  - checkpoint.py：mark → done → status 分支 1（产物 + exit_code=0 → 跳过）
  - design_impl_check.py：stage10 基线 criterion 未挂接 / 悬空引用报 MAPPING_CRITERION；
    基线无 C 编号时豁免不卡
"""

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import input_card_check  # noqa: E402
from design_impl_check import check_project  # noqa: E402

SCHEMA = input_card_check._load_schema(input_card_check.DEFAULT_SCHEMA)

MAPPING_HEADER = (
    "| 编号 | 设计来源 | 设计项（功能/链路） | 验收指标 | 端到端链路 | 用户操作路径 | 实现落点 | 状态 | 验证证据 |\n"
    "|---|---|---|---|---|---|---|---|---|\n"
)


def _good_card() -> dict:
    return {
        "step": "5A",
        "project": "demo",
        "updated_at": "2026-11-11 14:30",
        "sources": ["02_架构设计/第一轮技术架构设计文档.md"],
        "arch_ref": "02_架构设计/第一轮技术架构设计文档.md",
        "mock_policy": "外部依赖 Mock",
        "ports": {"backend": 8083},
        "tasks": [{"task_id": "T01", "desc": "实现工作流 CRUD", "risk": "高", "criterion_ref": ["C01"]}],
        "scope": {
            "files_in_scope": ["05_代码/backend/**"],
            "out_of_scope": ["05_代码/frontend/**"],
        },
        "limits": {"max_files": 12, "max_attempts": 3, "timeout_min": 20},
    }


# ---------- G1 输入卡校验 ----------

def test_good_card_passes(tmp_path):
    (tmp_path / "02_架构设计").mkdir(parents=True)
    (tmp_path / "02_架构设计" / "第一轮技术架构设计文档.md").write_text("# arch", encoding="utf-8")
    errs = input_card_check.check_card("5A", _good_card(), SCHEMA, tmp_path)
    assert errs == [], errs


def test_bad_card_reports_errors(tmp_path):
    card = _good_card()
    card["sources"] = ["../../../etc/passwd"]
    card["scope"] = {
        "files_in_scope": ["05_代码/backend/**"],
        "out_of_scope": ["05_代码/backend/**"],
    }
    card["limits"] = {"max_files": 0}
    card["tasks"][0]["risk"] = "极高"
    errs = input_card_check.check_card("5A", card, SCHEMA, tmp_path)
    assert any("越出" in e for e in errs)
    assert any("自相矛盾" in e for e in errs)
    assert any("正整数" in e for e in errs)
    assert any("risk 枚举" in e for e in errs)


def test_card_cli_exit_codes(tmp_path):
    """子进程口径：合法卡 0，非法卡 1。"""
    card_dir = tmp_path / "card"
    card_dir.mkdir()
    good = card_dir / "good.yaml"
    good.write_text(
        "step: 5A\nproject: demo\nupdated_at: '2026-11-11 14:30'\n"
        "sources: [02_架构设计/第一轮技术架构设计文档.md]\narch_ref: x\nmock_policy: m\nports: {backend: 8083}\n"
        "tasks: [{task_id: T01, desc: x}]\n"
        "scope: {files_in_scope: [a/**], out_of_scope: [b/**]}\n"
        "limits: {max_files: 3, max_attempts: 2, timeout_min: 10}\n",
        encoding="utf-8",
    )
    ok = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "input_card_check.py"), "5A", str(good)],
        capture_output=True, text=True,
    )
    assert ok.returncode == 0, ok.stdout + ok.stderr

    bad = card_dir / "bad.yaml"
    bad.write_text("step: 5A\nproject: ''\nupdated_at: '2026/11/11'\nsources: []\n", encoding="utf-8")
    # 旁路观察期：非法卡仅警告、exit 0
    ng = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "input_card_check.py"), "5A", str(bad)],
        capture_output=True, text=True,
    )
    assert ng.returncode == 0, ng.stdout + ng.stderr
    assert "待核" in ng.stdout

    # --strict 转阻塞闸：非法卡 exit 1
    ng_strict = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "input_card_check.py"), "5A", str(bad), "--strict"],
        capture_output=True, text=True,
    )
    assert ng_strict.returncode == 1, ng_strict.stdout + ng_strict.stderr


# ---------- G10 断点脚本 ----------

def test_checkpoint_mark_done_status(tmp_path):
    root = tmp_path / "proj"
    root.mkdir()
    (root / "06_冒烟").mkdir(parents=True)
    (root / "06_冒烟" / "冒烟记录.md").write_text("# smoke", encoding="utf-8")
    script = str(ROOT / "scripts" / "checkpoint.py")

    mark = subprocess.run(
        [sys.executable, script, "mark", str(root), "--step", "6",
         "--command", "npm run dev", "--output-path", "06_冒烟/冒烟记录.md"],
        capture_output=True, text=True,
    )
    assert mark.returncode == 0, mark.stdout + mark.stderr

    done = subprocess.run(
        [sys.executable, script, "done", str(root), "--step", "6", "--exit-code", "0"],
        capture_output=True, text=True,
    )
    assert done.returncode == 0, done.stdout + done.stderr

    status = subprocess.run(
        [sys.executable, script, "status", str(root)],
        capture_output=True, text=True,
    )
    assert status.returncode == 0, status.stdout + status.stderr
    assert "分支 1" in status.stdout  # 产物存在 + exit_code=0 → 跳过


def test_checkpoint_no_marker(tmp_path):
    root = tmp_path / "proj"
    root.mkdir()
    status = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "checkpoint.py"), "status", str(root)],
        capture_output=True, text=True,
    )
    assert status.returncode == 0
    assert "无标记文件" in status.stdout


# ---------- G8 指标挂接核对 ----------

def _write_project(root: Path, baseline: str, mapping_rows: str):
    root.mkdir(parents=True, exist_ok=True)
    (root / "01_项目基线说明书.md").write_text(baseline, encoding="utf-8")
    (root / "_设计实施映射表.md").write_text(MAPPING_HEADER + mapping_rows, encoding="utf-8")


def test_g8_all_criteria_mapped_ok(tmp_path):
    root = tmp_path / "proj"
    _write_project(
        root,
        "## 核心指标\n- C01 登录 3 秒内返回\n- C02 列表 20 条分页\n",
        "| D-01 | 架构 | 链路A | C01 | 输入→处理→输出 | 路径 | backend/a.py | ✅已实现已验证 | curl /x 200 |\n"
        "| D-02 | 架构 | 链路B | C02 | 输入→处理→输出 | 路径 | backend/b.py | ✅已实现已验证 | curl /y 200 |\n",
    )
    r = check_project(root, stage="10", min_rows=0)
    assert r["status"] == "OK", r["details"]


def test_g8_unmapped_criterion_blocked(tmp_path):
    root = tmp_path / "proj"
    _write_project(
        root,
        "## 核心指标\n- C01 登录 3 秒内返回\n- C02 列表 20 条分页\n",
        "| D-01 | 架构 | 链路A | C01 | 输入→处理→输出 | 路径 | backend/a.py | ✅已实现已验证 | curl /x 200 |\n"
        "| D-02 | 架构 | 链路B | — | 输入→处理→输出 | 路径 | backend/b.py | ✅已实现已验证 | curl /y 200 |\n",
    )
    r = check_project(root, stage="10", min_rows=0, strict_criterion=True)
    assert r["status"] == "MAPPING_CRITERION"
    assert "C02" in r["details"]


def test_g8_dangling_reference_blocked(tmp_path):
    root = tmp_path / "proj"
    _write_project(
        root,
        "## 核心指标\n- C01 登录 3 秒内返回\n",
        "| D-01 | 架构 | 链路A | C01, C99 | 输入→处理→输出 | 路径 | backend/a.py | ✅已实现已验证 | curl /x 200 |\n",
    )
    r = check_project(root, stage="10", min_rows=0, strict_criterion=True)
    assert r["status"] == "MAPPING_CRITERION"
    assert "C99" in r["details"]


def test_g8_criterion_bypass_by_default(tmp_path):
    """方案 §8：新闸默认旁路观察期——未挂接只记 warning，不阻塞交付。"""
    root = tmp_path / "proj"
    _write_project(
        root,
        "## 核心指标\n- C01 登录 3 秒内返回\n- C02 列表 20 条分页\n",
        "| D-01 | 架构 | 链路A | C01 | 输入→处理→输出 | 路径 | backend/a.py | ✅已实现已验证 | curl /x 200 |\n"
        "| D-02 | 架构 | 链路B | — | 输入→处理→输出 | 路径 | backend/b.py | ✅已实现已验证 | curl /y 200 |\n",
    )
    r = check_project(root, stage="10", min_rows=0)  # 缺省旁路
    assert r["status"] == "OK"
    assert "C02" in r["criterion_warning"]


def test_g8_no_criterion_in_baseline_exempt(tmp_path):
    """基线没有 C 编号（历史/未改造项目）→ 跳过挂接核对，不判红。"""
    root = tmp_path / "proj"
    _write_project(
        root,
        "## 核心指标\n- 登录快速返回\n",
        "| D-01 | 架构 | 链路A | — | 输入→处理→输出 | 路径 | backend/a.py | ✅已实现已验证 | curl /x 200 |\n",
    )
    r = check_project(root, stage="10", min_rows=0)
    assert r["status"] == "OK", r["details"]
