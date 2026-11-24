#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""L4：端到端主链路（直连 + 云函数代理），只覆盖 P0 主路径。"""
import pytest

from api.auth_api import login_api
from api.booking_api import create_booking, my_bookings
from api.cloud_api import proxy_action
from api.package_api import package_detail, packages
from common.assert_util import assert_ok
from common.data_util import days_from_today, idem_key, next_phone
from common.request_util import ApiClient

pytestmark = pytest.mark.l4


def test_full_business_chain_direct(cfg, mysql, redis):
    """登录 → 浏览列表 → 详情 → 提交预约 → 我的列表可见 → 重复提交幂等。"""
    anon = ApiClient(cfg["base_url"], name="e2e")
    account = cfg["accounts"]["demo"]
    session = assert_ok(login_api(anon, account["account"], account["password"]))
    token = session["token"]

    api = ApiClient(cfg["base_url"], token=token, name="e2e-demo")
    lst = assert_ok(packages(api, 1, 10))
    assert lst["total"] == 4
    pkg = lst["list"][1]
    detail = assert_ok(package_detail(api, pkg["id"]))
    assert detail["title"] == pkg["title"]

    phone, date, slot = next_phone(), days_from_today(13), "上午"
    try:
        first = assert_ok(create_booking(api, pkg["id"], date, slot, phone, "E2E 直连"))
        assert first["duplicated"] is False
        second = assert_ok(create_booking(api, pkg["id"], date, slot, phone, "E2E 直连"))
        assert second["bookingId"] == first["bookingId"] and second["duplicated"] is True

        mine = assert_ok(my_bookings(api, 1, 20))
        ids_ = [x["id"] for x in mine["list"]]
        assert first["bookingId"] in ids_
        assert next(x for x in mine["list"] if x["id"] == first["bookingId"])["statusText"] == "待确认"
        assert mysql.scalar(f"SELECT COUNT(*) FROM booking WHERE id={first['bookingId']}") == "1"
    finally:
        rows = mysql.query(f"SELECT id FROM booking WHERE contact='{phone}'")
        if rows:
            bid = rows[0][0]
            mysql.execute(f"DELETE FROM notify_log WHERE booking_id={bid}")
            mysql.execute(f"DELETE FROM booking WHERE id={bid}")
        redis.delete(idem_key(phone, date, slot))


def test_full_business_chain_via_cloud_function(cfg, mysql, redis):
    """云函数代理链路：login → packages → detail → createBooking → myBookings。"""
    cf = ApiClient(cfg["cf_url"], name="e2e-cf")
    account = cfg["accounts"]["demo"]
    session = assert_ok(proxy_action(cf, "login", {
        "account": account["account"], "password": account["password"]}))
    token = session["token"]

    lst = assert_ok(proxy_action(cf, "packages", {"page": 1, "size": 10}))
    assert lst["total"] == 4
    detail = assert_ok(proxy_action(cf, "packageDetail", {"id": 1}))
    assert detail["id"] == 1

    phone, date, slot = next_phone(), days_from_today(14), "晚间"
    try:
        created = assert_ok(proxy_action(cf, "createBooking", {
            "packageId": 1, "bookDate": date, "slot": slot, "contact": phone,
            "remark": "E2E 云函数"}, token=token))
        mine = assert_ok(proxy_action(cf, "myBookings", {"page": 1, "size": 20}, token=token))
        assert created["bookingId"] in [x["id"] for x in mine["list"]]
    finally:
        rows = mysql.query(f"SELECT id FROM booking WHERE contact='{phone}'")
        if rows:
            bid = rows[0][0]
            mysql.execute(f"DELETE FROM notify_log WHERE booking_id={bid}")
            mysql.execute(f"DELETE FROM booking WHERE id={bid}")
        redis.delete(idem_key(phone, date, slot))


def test_h5_entry_reachable(cfg):
    client = ApiClient(cfg["h5_url"], name="h5")
    # H5 dev server 对 Accept: application/json 回 404（按浏览器口径取 text/html）
    resp = client.get("/", headers={"Accept": "text/html"}, timeout=10)
    assert resp.status == 200
    assert "<!DOCTYPE html>" in resp.text or "<html" in resp.text.lower()
