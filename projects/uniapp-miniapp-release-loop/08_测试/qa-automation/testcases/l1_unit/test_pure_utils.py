#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""L1 单元测试（纯函数/工具/契约静态校验，不碰 DB/HTTP）。

另有后端 JUnit（PasswordHasher 5 条 + JwtService 5 条）由 test_maven_unit.py 调起，
是真正的核心工具类单测；本文件覆盖测试侧纯函数与静态契约。
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from common.data_util import idem_key, mask, next_phone  # noqa: E402
from common.sql_util import Mysql  # noqa: E402

pytestmark = pytest.mark.l1

PROJECT = Path(__file__).resolve().parents[4]


def test_idem_key_contract():
    """幂等键 = ub:idem:booking:{sha256(phone|date|slot)[:32]}，且不落手机号明文。"""
    key = idem_key("13900001234", "2026-12-01", "上午")
    assert key.startswith("ub:idem:booking:")
    assert len(key) == len("ub:idem:booking:") + 32
    assert re.fullmatch(r"[0-9a-f]{32}", key.rsplit(":", 1)[1])
    assert "13900001234" not in key
    assert key == idem_key("13900001234", "2026-12-01", "上午")
    assert key != idem_key("13900001234", "2026-12-01", "下午")


def test_phone_generator_matches_backend_pattern():
    """用例生成的手机号必须过 BookingRequest 的 ^1[3-9]\\d{9}$，且 100 个不重复。"""
    phones = [next_phone() for _ in range(100)]
    assert all(re.fullmatch(r"1[3-9]\d{9}", p) for p in phones)
    assert len(set(phones)) == 100


def test_mask_phone_contract():
    assert mask("13900001234") == "139****1234"
    assert mask("123") == "123"
    assert mask("") == ""


def test_sql_quote_escapes_single_quote():
    """清理 SQL 的引号转义：不让测试数据拼串破坏语句。"""
    assert Mysql.quote("O'Reilly") == "'O''Reilly'"
    assert Mysql.quote(3) == "'3'"


def test_openapi_contract_shape():
    """C12 静态面：契约 5 路径 / 6 操作，路径与操作不得漂移。"""
    doc = json.loads((PROJECT / "06.5_契约" / "openapi.json").read_text(encoding="utf-8"))
    paths = doc["paths"]
    assert set(paths) == {"/api/bookings", "/api/auth/logout", "/api/auth/login",
                          "/api/packages", "/api/packages/{id}"}
    ops = {(path, method) for path, methods in paths.items() for method in methods}
    assert len(ops) == 6
    assert ("/api/bookings", "post") in ops and ("/api/bookings", "get") in ops
    assert ("/api/packages", "get") in ops and ("/api/packages/{id}", "get") in ops


def test_p0_cases_json_schema():
    """p0_cases.json 可被 scripts/p0_regression_test.py 直接消费：字段齐全、ID 唯一。"""
    raw = json.loads((PROJECT / "08_测试" / "p0_cases.json").read_text(encoding="utf-8"))
    cases = raw["cases"] if isinstance(raw, dict) else raw
    assert len(cases) >= 10
    assert len({c["id"] for c in cases}) == len(cases)
    for case in cases:
        for field in ("id", "name", "method", "url", "expect_status"):
            assert field in case, f"缺字段 {field}: {case}"
        assert case["url"].startswith("http://127.0.0.1:")


def test_env_config_gate(cfg):
    """测试库口径固定 3307（Q-024），阈值与基线一致。"""
    assert cfg["mysql"]["port"] == 3307
    assert cfg["thresholds"]["c03_p95_ms"] == 800
    assert cfg["thresholds"]["c04_cache_hit_ratio"] == 0.80
    assert cfg["thresholds"]["booking_window_days"] == 30


def test_maven_unit_tests_green():
    """跑后端 JUnit（10 条：PasswordHasher 5 + JwtService 5），0 失败才算 L1 绿。"""
    import shutil
    backend = PROJECT / "05_代码" / "backend" / "booking-service"
    assert (backend / "pom.xml").exists()
    mvn = os.environ.get("MVN_BIN") or shutil.which("mvn")
    assert mvn, "未找到 mvn（PATH 里需有 mvn.cmd，或设 MVN_BIN 指向绝对路径）"
    proc = subprocess.run(
        [mvn, "-q", "-Dtest=PasswordHasherTest,JwtServiceTest", "test"],
        cwd=str(backend), capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=300,
    )
    out = (proc.stdout or "") + "\n" + (proc.stderr or "")
    assert proc.returncode == 0, f"mvn test 失败：\n{out[-3000:]}"
    reports = list((backend / "target" / "surefire-reports").glob("*.txt"))
    assert reports, f"未生成 surefire 报告：{out[-1000:]}"
    text = "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in reports)
    assert "Failures: 0" in text and "Errors: 0" in text, text[-2000:]
    print("\nJUnit 汇总:\n" + "\n".join(line for line in text.splitlines() if "Tests run" in line))
