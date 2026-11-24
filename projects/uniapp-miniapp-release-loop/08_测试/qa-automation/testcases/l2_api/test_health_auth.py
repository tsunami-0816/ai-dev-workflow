#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""L2：健康检查 + 登录/登出四象限（正向/反向/边界/未授权）。"""
import pytest

from api.auth_api import login_api, login_openid, logout_api
from api.booking_api import my_bookings
from api.health_api import health
from common.assert_util import assert_err, assert_ok
from common.request_util import ApiClient

pytestmark = pytest.mark.l2


def test_health_up_with_three_components(admin):
    resp = health(admin)
    assert resp.status == 200, resp.text[:300]
    data = resp.body
    assert data["status"] == "UP"
    for component in ("db", "redis", "rabbit"):
        assert component in data["components"], f"health 缺组件 {component}"
        assert data["components"][component]["status"] == "UP", f"{component} 非 UP"


def test_login_success_returns_full_session(admin, cfg):
    account = cfg["accounts"]["demo"]
    resp = login_api(admin, account["account"], account["password"])
    data = assert_ok(resp)
    assert data["userId"] > 0
    assert len(data["token"]) > 100
    assert data["expiresIn"] == 7200
    assert data["nickname"] == "演示用户A"


def test_login_wrong_password(admin):
    resp = login_api(admin, "demo", "wrong-pass")
    assert_err(resp, 401, 40101)


def test_autoprovisioned_account_can_login(admin, mysql):
    """账号兜底链路：测试侧补种的 PBKDF2 哈希必须被后端接受（无注册接口时的替代）。"""
    import time

    from common.account_util import delete_account, ensure_account

    name = f"qa_auto_{int(time.time())}"
    try:
        ensure_account(mysql, name, "welcome1", "QA 自动补种")
        resp = login_api(admin, name, "welcome1")
        data = assert_ok(resp)
        assert data["userId"] > 0 and data["nickname"] == "QA 自动补种"
    finally:
        delete_account(mysql, name)


def test_login_unknown_account(admin):
    resp = login_api(admin, "no-such-user", "welcome1")
    assert_err(resp, 401, 40101)


def test_login_empty_credentials(admin):
    resp = login_api(admin, "", "")
    assert_err(resp, 400, 40001)


def test_login_account_over_32_chars(admin):
    resp = login_api(admin, "a" * 33, "welcome1")
    assert_err(resp, 400, 40001)


def test_login_openid_direct_h5_rejected(admin):
    """Q-004 回归：H5 直连凭 openid 建号必须 40102，且不新建用户。"""
    resp = login_openid(admin, "o_direct_h5_should_fail", "直连冒充")
    assert_err(resp, 401, 40102)


def test_token_usable_for_protected_api(admin, cfg):
    account = cfg["accounts"]["demo"]
    token, user_id = _login(cfg, account)
    client = ApiClient(cfg["base_url"], token=token, name="fresh")
    data = assert_ok(my_bookings(client))
    assert data["total"] >= 0
    assert isinstance(data["list"], list)


def _login(cfg, account):
    resp = login_api(ApiClient(cfg["base_url"], name="tmp"), account["account"], account["password"])
    data = assert_ok(resp)
    return data["token"], data["userId"]


def test_logout_invalidates_old_token(cfg):
    account = cfg["accounts"]["demo"]
    token, _ = _login(cfg, account)
    client = ApiClient(cfg["base_url"], token=token, name="logout")
    logout = logout_api(client)
    assert_ok(logout, expect_data=False)
    resp = my_bookings(client)
    assert_err(resp, 401, 40103)


def test_no_token_rejected(admin):
    assert_err(my_bookings(admin), 401, 40101)


def test_malformed_token_rejected(cfg):
    client = ApiClient(cfg["base_url"], token="x.y.z", name="bad")
    assert_err(my_bookings(client), 401, 40101)


def test_logout_without_token_rejected(admin):
    assert_err(logout_api(admin), 401, 40101)
