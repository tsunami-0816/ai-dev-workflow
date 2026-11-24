#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""统一断言：POST 同时接受 200/201（规则 10）；不只断 HTTP，还断业务字段（G6）。"""


def assert_ok(resp, expect_data=True):
    assert resp.status in (200, 201), f"期望 200/201，实际 {resp.status}: {resp.text[:300]}"
    assert isinstance(resp.body, dict) and resp.body.get("code") == 0, \
        f"期望 code=0，实际 {resp.text[:300]}"
    if expect_data:
        assert resp.data() is not None, f"期望 data 非空: {resp.text[:300]}"
    return resp.data()


def assert_err(resp, status, code):
    assert resp.status == status, f"期望 HTTP {status}，实际 {resp.status}: {resp.text[:300]}"
    assert resp.body.get("code") == code, f"期望 code={code}，实际 {resp.text[:300]}"
    return resp.body


def assert_fields(obj, **expected):
    for key, value in expected.items():
        assert key in obj, f"缺少字段 {key}: {obj}"
        assert obj[key] == value, f"字段 {key} 期望 {value}，实际 {obj[key]}"
