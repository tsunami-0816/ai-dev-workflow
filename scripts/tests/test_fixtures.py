#!/usr/bin/env python3
"""工作流自检测试（pytest 真断言，非打印式）。

运行：python -m pytest scripts/tests -q
依赖：pip install -e ".[test]"（PyYAML + pytest）

覆盖三类：
1. 校验脚本核心纯函数（_norm / 日期解析 / 映射表常量）
2. 真实仓库的一致性校验必须绿
3. 负向 fixture：在临时仓库副本里故意制造文档漂移，校验器必须报红。
   这类用例专门防止「把校验放宽」被误当成修复——2026-11-09 主控重构时
   wf steps --check 曾 30 项红，修法必须是改数据源，不能是关掉检查。
"""

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from api_contract_validator import _norm
from design_impl_check import EVIDENCE_PLACEHOLDERS, REQUIRED_COLUMNS

SPEC_FILES = [
    "WORKFLOW_工作流主控.md",
    "WORKFLOW_步骤定义.md",
    "WORKFLOW_规则库.md",
    "WORKFLOW_卡点协议.md",
    "WORKFLOW_执行约定.md",
]
COPIED_ROOT_FILES = SPEC_FILES + ["WORKFLOW_项目队列.md"]
# P1-1：4 个规则副本载体（AGENTS.md + 三份同构指针）必须在临时副本里，否则 steps --check 判缺失
COPIED_RULE_CARRIERS = [
    "AGENTS.md",
    ".github/copilot-instructions.md",
    ".trae/rules/project_rules.md",
    ".cursor/rules/workflow.mdc",
]


def _wf_cmd():
    """优先用已安装的 wf；未安装时退回 python -m（CI 里两者都可用）。"""
    exe = shutil.which("wf")
    if exe:
        return [exe]
    return [sys.executable, "-m", "workflow_cli.cli"]


def _run(args, cwd):
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(
        _wf_cmd() + list(args),
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _make_fake_root(tmp_path):
    """复制校验器会读到的最小仓库，供负向测试随意破坏（不碰真实文件）。"""
    dst = tmp_path / "wf_copy"
    dst.mkdir()
    for name in COPIED_ROOT_FILES:
        shutil.copy2(ROOT / name, dst / name)
    for rel in COPIED_RULE_CARRIERS:
        target = dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, target)
    shutil.copytree(ROOT / "workflow", dst / "workflow")
    shutil.copytree(ROOT / "prompts", dst / "prompts")
    shutil.copytree(
        ROOT / "projects" / "_TEMPLATE_新项目",
        dst / "projects" / "_TEMPLATE_新项目",
    )
    (dst / "scripts").mkdir()
    for p in sorted((ROOT / "scripts").glob("*.py")):
        shutil.copy2(p, dst / "scripts" / p.name)
    return dst


@pytest.fixture
def fake_root(tmp_path):
    root = _make_fake_root(tmp_path)
    result = _run(["steps", "--check"], root)
    assert result.returncode == 0, (
        "临时副本本身必须先自洽，否则负向测试没有意义：\n"
        + result.stdout + result.stderr
    )
    return root


# ---------- 1. 核心纯函数 ----------

def test_norm_path():
    """路径归一化：契约脚本曾因此误报 3 次"""
    cases = [
        ("/api/v1/tickets/123", "/api/v1/tickets/{id}"),
        ("/api/v1/tickets/{ticket_id}", "/api/v1/tickets/{id}"),
        ("/api/v1/tickets/${id}", "/api/v1/tickets/{id}"),
        ("/api/v1/tickets/:id", "/api/v1/tickets/{id}"),
        ("/api/v1/users/456/posts", "/api/v1/users/{id}/posts"),
        ("/api/v1/workflows", "/api/v1/workflows"),
        ("/api/v1/metrics/summary?range_days=7", "/api/v1/metrics/summary"),
        ("/", "/"),
    ]
    for inp, expected in cases:
        assert _norm(inp) == expected, f"_norm({inp!r}) != {expected!r}"


def test_parse_date():
    """门禁脚本的创建日期解析"""
    pattern = re.compile(r"创建日期[：:]\s*\**\s*(\d{4}-\d{2}-\d{2})")
    cases = [
        ("创建日期：2026-11-02", "2026-11-02"),
        ("创建日期：**2026-11-02**", "2026-11-02"),
        ("创建日期：**2026-11-02**（翻新建档）", "2026-11-02"),
        ("创建日期： 2026-11-02", "2026-11-02"),
        ("创建日期: 2026-11-02", "2026-11-02"),
    ]
    for inp, expected in cases:
        m = pattern.search(inp)
        assert (m.group(1) if m else None) == expected, f"parse_date({inp!r})"


def test_design_impl_constants():
    """映射表必需列与证据占位值"""
    assert REQUIRED_COLUMNS == [
        "编号", "设计来源", "设计项", "端到端链路", "用户操作路径",
        "实现落点", "状态", "验证证据",
    ]
    for placeholder in ["", "无", "待补", "todo", "tbd", "n/a"]:
        assert placeholder in EVIDENCE_PLACEHOLDERS


def test_spec_files_exist():
    """专项文件缺失时一致性校验会整片报红，先守住文件本身"""
    for name in SPEC_FILES:
        assert (ROOT / name).is_file(), f"缺少专项文件：{name}"


def test_steps_yaml_structure():
    yaml = pytest.importorskip("yaml")
    cfg = yaml.safe_load((ROOT / "workflow" / "steps.yaml").read_text(encoding="utf-8"))
    steps = cfg["steps"]
    ids = [str(s["id"]) for s in steps]
    assert len(ids) == len(set(ids)), "步骤 id 重复"
    for s in steps:
        assert s.get("id") and s.get("name") and s.get("owner"), f"步骤字段不全：{s}"
        for art in s.get("artifacts") or []:
            assert art.get("path"), f"{s['id']} 的 artifacts 缺 path"
    design_ids = {str(d["id"]) for d in cfg["design_module"]}
    assert design_ids == {"0.1", "0.2", "0.3", "0.4", "0.5"}


# ---------- 2. 真实仓库必须绿 ----------

def test_live_steps_check_is_green():
    result = _run(["steps", "--check"], ROOT)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "🟢" in result.stdout


def test_live_queue_check_is_green():
    result = _run(["queue", "--check", "--allow-missing"], ROOT)
    assert result.returncode == 0, result.stdout + result.stderr


# ---------- 3. 负向 fixture：校验器必须能抓到漂移 ----------

def test_check_detects_step_table_drift(fake_root):
    """步骤定义表删一行 → 必须报「步骤定义表缺行」"""
    path = fake_root / "WORKFLOW_步骤定义.md"
    original = path.read_text(encoding="utf-8").splitlines()
    lines = [ln for ln in original if not ln.startswith("| 6.5 |")]
    assert len(lines) == len(original) - 1, "未成功删掉 6.5 行"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    result = _run(["steps", "--check"], fake_root)
    assert result.returncode != 0, "删了步骤却仍然判绿 = 校验失效"
    assert "步骤定义表缺行" in result.stdout and "6.5" in result.stdout


def test_check_detects_rulebook_drift(fake_root):
    """规则库 8.0 登记表删一行 → 必须报「登记表缺行」"""
    path = fake_root / "WORKFLOW_规则库.md"
    original = path.read_text(encoding="utf-8").splitlines()
    lines = [ln for ln in original if not ln.startswith("| R9 |")]
    assert len(lines) == len(original) - 1, "未成功删掉 R9 登记行"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    result = _run(["steps", "--check"], fake_root)
    assert result.returncode != 0, "登记表漏行却仍然判绿 = 校验失效"
    assert "登记表缺行" in result.stdout


def test_check_detects_flowchart_drift(fake_root):
    """主控流程图漏步骤 → 必须报「流程图缺少步骤」"""
    path = fake_root / "WORKFLOW_工作流主控.md"
    text = path.read_text(encoding="utf-8")
    assert "10.6 简历适配产出" in text
    path.write_text(text.replace("10.6 简历适配产出", "简历适配产出"), encoding="utf-8")
    result = _run(["steps", "--check"], fake_root)
    assert result.returncode != 0, "流程图漏步骤却仍然判绿 = 校验失效"
    assert "流程图缺少步骤 10.6" in result.stdout


def test_check_detects_missing_prompt(fake_root):
    """提示词文件丢失 → 必须报「提示词不存在」"""
    prompt = fake_root / "prompts" / "step02_技术架构设计.md"
    prompt.unlink()
    result = _run(["steps", "--check"], fake_root)
    assert result.returncode != 0, "提示词缺失却仍然判绿 = 校验失效"
    assert "提示词不存在" in result.stdout


# ---------- 4. 10.0 完成门禁：防「否定式通过」+ 不误伤历史项目 ----------

def test_gate_artifacts_all_have_forbid():
    """凡靠 keywords 判通过的产物，都必须配 forbid 兜住否定式文本"""
    yaml = pytest.importorskip("yaml")
    cfg = yaml.safe_load((ROOT / "workflow" / "steps.yaml").read_text(encoding="utf-8"))
    for step in cfg["steps"]:
        for art in step.get("artifacts") or []:
            if art.get("keywords"):
                assert art.get("forbid"), (
                    f"{step['id']}/{art['path']} 只有 keywords 没有 forbid，"
                    "写「未通过」也会命中「通过」"
                )


def test_gate_check_rejects_negative_conclusion(tmp_path):
    """check_one 必须能抓到「结论：未通过」这类绕过，正常报告则放行"""
    import workflow_completion_check as gate

    item = {
        "path": "report.md",
        "label": "契约校验记录",
        "keywords": ["通过"],
        "forbid": ["未通过"],
        "min_bytes": 10,
    }
    report = tmp_path / "report.md"
    report.write_text("契约校验结论：未通过，仍存在不一致接口。", encoding="utf-8")
    bad = gate.check_one(tmp_path, item)
    assert bad["status"] == "NEGATIVE", f"否定式结论没被拦住：{bad}"

    report.write_text("契约校验通过，0 个臆造接口，结论：PASS。", encoding="utf-8")
    good = gate.check_one(tmp_path, item)
    assert good["status"] == "OK", f"正常报告被误判：{good}"


def test_gate_forbid_no_false_positive_on_history():
    """新增 forbid 不得让已交付的 8 个项目集体变红"""
    yaml = pytest.importorskip("yaml")
    import workflow_completion_check as gate

    cfg = yaml.safe_load((ROOT / "workflow" / "steps.yaml").read_text(encoding="utf-8"))
    projects = [d for d in (ROOT / "projects").iterdir()
                if d.is_dir() and not d.name.startswith("_")]
    checked = 0
    for proj in projects:
        for step in cfg["steps"]:
            for art in step.get("artifacts") or []:
                if not art.get("forbid"):
                    continue
                result = gate.check_one(proj, gate._gate_item(art, step, False))
                assert result["status"] != "NEGATIVE", (
                    f"{proj.name}/{art['path']} 被 forbid 误伤：{result.get('forbid_hit')}"
                )
                checked += 1
    assert checked > 0, "没有检查到任何历史产物，用例本身失效"


# ---------- 5. 新增产物按创建日期豁免 + 接口形态/前端降级 + G8 基线缺失 ----------

def _write_board(root: Path, *lines: str):
    (root / "_项目状态.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _item(path: str, **extra) -> dict:
    base = {"path": path, "keywords": [], "forbid": [], "min_bytes": 10}
    base.update(extra)
    return base


def test_gate_new_project_requires_resume_artifacts(tmp_path):
    """2026-11-11 起创建的项目：缺简历产物 / 自迭代报告必须判 MISSING"""
    import workflow_completion_check as gate

    _write_board(tmp_path, "- 创建日期：2026-11-11")
    resume = gate._gate_item(
        _item("10_交付/简历项目描述.md", launch_date="2026-11-11"),
        {"id": "10.6", "fallback": ["10.6"]}, False,
    )
    assert gate.check_one(tmp_path, resume)["status"] == "MISSING"

    retro = gate._gate_item(
        _item("10_交付/工作流自迭代报告.md", launch_date="2026-11-11"),
        {"id": "11", "fallback": ["11"]}, False,
    )
    assert gate.check_one(tmp_path, retro)["status"] == "MISSING"


def test_gate_old_project_exempts_new_artifacts(tmp_path):
    """创建日期早于上线日：同样缺文件应 OK + skipped，不判红"""
    import workflow_completion_check as gate

    _write_board(tmp_path, "- 创建日期：2026-11-01")
    item = gate._gate_item(
        _item("10_交付/简历项目描述.md", launch_date="2026-11-11"),
        {"id": "10.6", "fallback": ["10.6"]}, False,
    )
    r = gate.check_one(tmp_path, item)
    assert r["status"] == "OK" and r.get("skipped"), r


def test_gate_openapi_skipped_for_non_http(tmp_path):
    """看板接口形态=二进制时跳过 OpenAPI；HTTP 或缺省则必须交"""
    import workflow_completion_check as gate

    item = gate._gate_item(
        _item("06.5_契约/openapi.json", requires_http_api=True),
        {"id": "6.5", "fallback": ["6.5"]}, False,
    )
    _write_board(tmp_path, "- **接口形态**：二进制")
    r = gate.check_one(tmp_path, item)
    assert r["status"] == "OK" and "非 HTTP" in r.get("skipped", ""), r

    _write_board(tmp_path, "- **接口形态**：HTTP")
    assert gate.check_one(tmp_path, item)["status"] == "MISSING"


def test_gate_f2_ui_report_skipped_without_frontend(tmp_path):
    """纯后端翻新项目不要求交前端 UI 报告"""
    import workflow_completion_check as gate

    item = gate._gate_item(
        _item("F2_体检/前端UI质量报告.md", requires_frontend=True),
        {"id": "F2", "fallback": ["F2"]}, True,
    )
    _write_board(tmp_path, "- **路线**：翻新\n- 本项目无前端")
    r = gate.check_one(tmp_path, item)
    assert r["status"] == "OK" and r.get("skipped"), r


def test_g8_baseline_missing_is_warned(tmp_path):
    """基线缺失不再静默豁免：旁路观察期告警，strict 转阻塞"""
    from design_impl_check import check_project

    root = tmp_path / "proj"
    root.mkdir()
    (root / "_设计实施映射表.md").write_text(
        "| 编号 | 设计来源 | 设计项（功能/链路） | 验收指标 | 端到端链路 | 用户操作路径 | 实现落点 | 状态 | 验证证据 |\n"
        "|---|---|---|---|---|---|---|---|---|\n"
        "| D-01 | 架构 | 链路A | — | 输入→处理→输出 | 路径 | backend/a.py | ✅已实现已验证 | curl /x 200 |\n",
        encoding="utf-8",
    )
    r = check_project(root, stage="10", min_rows=0)
    assert r["status"] == "OK", r
    assert "BASELINE_MISSING" in r["baseline_warning"]

    strict = check_project(root, stage="10", min_rows=0, strict_criterion=True)
    assert strict["status"] == "MAPPING_CRITERION", strict
    assert "BASELINE_MISSING" in strict["details"]


# ---------- 6. 看板一致性闸：路径列不能再豁免「未开始」，旧项目降级 ----------

BOARD_TABLE = (
    "| 步骤 | 名称 | 状态 | 产物路径 | 完成时间 | 备注 |\n"
    "|---|---|---|---|---|---|\n"
    "| 1 | 基线 | {state} | `01_项目基线说明书.md` | | |\n"
)


def _board(created: str, stage: str, state: str, extra: str = "") -> str:
    return (
        "# 项目状态看板\n\n"
        f"- 创建日期：{created}\n"
        f"- 当前阶段：**{stage}**\n"
        f"- 总体状态：未开始 / 进行中 / 卡在人工 / 已交付\n{extra}\n"
        + BOARD_TABLE.format(state=state)
    )


def test_board_path_filled_but_state_not_started_is_stale(tmp_path):
    """产物路径列非空 + 状态列「未开始」→ 仍判 BOARD_STALE"""
    import workflow_completion_check as gate

    (tmp_path / "_项目状态.md").write_text(
        _board("2026-11-11", "第 1 步 · 项目基线定义（未开始）", "未开始"), encoding="utf-8"
    )
    r = gate.check_board_consistency(tmp_path)
    assert r["status"] == "BOARD_STALE", r


def test_board_closed_word_in_body_does_not_mask_table(tmp_path):
    """正文写「项目已闭环」不能豁免表格里的「未开始」"""
    import workflow_completion_check as gate

    (tmp_path / "_项目状态.md").write_text(
        _board("2026-11-11", "第 1 步", "未开始", extra="\n> 项目已闭环\n"), encoding="utf-8"
    )
    r = gate.check_board_consistency(tmp_path)
    assert r["status"] == "BOARD_STALE", r


def test_board_all_done_is_ok(tmp_path):
    """当前阶段已完成且表格完成态 → OK"""
    import workflow_completion_check as gate

    (tmp_path / "_项目状态.md").write_text(
        _board("2026-11-11", "已完成（第 11 步）", "已完成"), encoding="utf-8"
    )
    r = gate.check_board_consistency(tmp_path)
    assert r["status"] == "OK", r


def test_board_stale_old_project_downgraded(tmp_path):
    """创建日期早于 2026-11-11 的旧项目：同样滞后 → BOARD_FRESH_WARNING"""
    import workflow_completion_check as gate

    (tmp_path / "_项目状态.md").write_text(
        _board("2026-11-01", "第 1 步", "未开始"), encoding="utf-8"
    )
    r = gate.check_board_consistency(tmp_path)
    assert r["status"] == "BOARD_FRESH_WARNING", r
