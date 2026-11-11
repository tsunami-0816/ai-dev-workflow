#!/usr/bin/env python3
"""第 1 / 4 步机器闸门回归用例（方案 P0-3：正样例退出 0，负样例退出 1）。"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import step_gate_check as gate  # noqa: E402

STEP1_OK = """# 项目基线说明书

## 量化指标

| 指标 | 目标值 | 验证方式 |
|---|---|---|
| 首字响应时长 | ≤ 2s | 冒烟脚本 curl 采集 |
| 检索准确率 | ≥ 90% | 测试集回归报告 |

## 排除范围

- 不做多租户隔离
"""

STEP4_OK = """# 任务拆解与开发规范

## 角色权限矩阵

| 角色 | 可访问 | 禁止 |
|---|---|---|
| 管理员 | 全部接口 | — |
| 普通用户 | 只读接口 | 删除 |

## 异常分支

- 网络失败：重试 2 次后降级
- 数据为空：返回空列表并提示
- 重复提交：幂等键拦截

## 边界输入

- 超长文本：> 8000 字符截断
- 并发：100 并发压测
"""


def test_step1_positive():
    assert gate.check_step1(STEP1_OK) == []


def test_step1_missing_unit_and_verify_owner():
    bad = STEP1_OK.replace("| 首字响应时长 | ≤ 2s |", "| 首字响应时长 | 很快 |")
    bad = bad.replace("| 检索准确率 | ≥ 90% | 测试集回归报告 |", "| 检索准确率 | ≥ 90% | 待补 |")
    errors = gate.check_step1(bad)
    assert any("未量化" in e for e in errors), errors
    assert any("缺验证归属" in e for e in errors), errors


def test_step1_missing_exclusion_section():
    bad = STEP1_OK.split("## 排除范围")[0]
    errors = gate.check_step1(bad)
    assert any("排除范围" in e for e in errors), errors


def test_step4_positive():
    assert gate.check_step4(STEP4_OK) == []


def test_step4_missing_boundary_section():
    bad = STEP4_OK.split("## 边界输入")[0]
    errors = gate.check_step4(bad)
    assert any("缺少「边界输入」" in e for e in errors), errors


def test_step4_exception_coverage_too_low():
    bad = STEP4_OK.replace(
        "- 网络失败：重试 2 次后降级\n- 数据为空：返回空列表并提示\n- 重复提交：幂等键拦截",
        "- 网络失败：重试 2 次后降级",
    )
    errors = gate.check_step4(bad)
    assert any("异常分支" in e and "至少需 3 类" in e for e in errors), errors
