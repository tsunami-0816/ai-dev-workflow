#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""L2：CORS 预检回归（Q-001）+ 云函数代理链路（L8）。"""
import json
import uuid

import pytest

from api.booking_api import create_booking
from api.cloud_api import healthz, healthz_probe, proxy_action
from common.assert_util import assert_err, assert_ok
from common.data_util import days_from_today, idem_key, next_phone, today
from common.wait_util import wait_until

pytestmark = pytest.mark.l2

ORIGIN = "http://127.0.0.1:5186"


def test_cors_preflight_allows_h5_origin(admin):
    resp = admin.options("/api/bookings", headers={
        "Origin": ORIGIN,
        "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "authorization",
    })
    assert resp.status in (200, 204), resp.text[:200]
    allow_origin = resp.headers.get("Access-Control-Allow-Origin", "")
    assert allow_origin == ORIGIN, f"预检未回 ACAO: {resp.headers}"


def test_cors_actual_get_carries_allow_origin(admin):
    resp = admin.get("/api/packages?page=1&size=1", headers={"Origin": ORIGIN})
    assert resp.status == 200
    assert resp.headers.get("Access-Control-Allow-Origin") == ORIGIN


def test_cf_health_and_signed_probe(cf):
    resp = healthz(cf)
    assert resp.status == 200 and resp.body.get("status") == "UP", resp.text[:300]
    probe = healthz_probe(cf)
    assert probe.status == 200, probe.text[:300]
    assert probe.body.get("backendProbe", {}).get("code") == 0, probe.text[:300]


def test_cf_packages_forward(cf):
    data = assert_ok(proxy_action(cf, "packages", {"page": 1, "size": 2}))
    assert len(data["list"]) == 2 and data["total"] == 4


def test_cf_package_detail_forward(cf):
    data = assert_ok(proxy_action(cf, "packageDetail", {"id": 2}))
    assert data["id"] == 2 and data["title"] == "复古胶片"


def test_cf_login_forward(cf, cfg):
    data = assert_ok(proxy_action(cf, "login", {
        "account": cfg["accounts"]["demo"]["account"],
        "password": cfg["accounts"]["demo"]["password"]}))
    assert len(data["token"]) > 100 and data["nickname"] == "演示用户A"


def test_cf_unknown_action(cf):
    assert_err(proxy_action(cf, "no-such-action", {}), 400, 40001)


def test_cf_rejects_forged_userid_field(cf):
    resp = proxy_action(cf, "createBooking", {
        "packageId": 1, "bookDate": today(), "slot": "上午",
        "contact": next_phone(), "userId": 1})
    assert_err(resp, 400, 40001)


def test_cf_booking_create_and_idempotent(cf, account, mysql, redis):
    phone = next_phone()
    date, slot = days_from_today(10), "下午"
    body = {"packageId": 1, "bookDate": date, "slot": slot, "contact": phone,
            "remark": "L2 云函数链路"}
    try:
        first = assert_ok(proxy_action(cf, "createBooking", body, token=account["token"]))
        assert first["duplicated"] is False
        second = assert_ok(proxy_action(cf, "createBooking", body, token=account["token"]))
        assert second["bookingId"] == first["bookingId"] and second["duplicated"] is True
        assert mysql.scalar(f"SELECT COUNT(*) FROM booking WHERE contact='{phone}' "
                            f"AND book_date='{date}' AND slot='{slot}'") == "1"
        wait_until(lambda: mysql.scalar(
            f"SELECT COUNT(*) FROM notify_log WHERE booking_id={first['bookingId']}") == "1",
            timeout=15, message="云函数链路 notify_log 未落库")
    finally:
        ids = mysql.query(f"SELECT id FROM booking WHERE contact='{phone}'")
        if ids:
            booking_id = ids[0][0]
            mysql.execute(f"DELETE FROM notify_log WHERE booking_id={booking_id}")
            mysql.execute(f"DELETE FROM booking WHERE id={booking_id}")
        redis.delete(idem_key(phone, date, slot))


def test_cf_list_my_bookings(cf, account):
    data = assert_ok(proxy_action(cf, "myBookings", {"page": 1, "size": 5},
                                  token=account["token"]))
    assert data["page"] == 1 and data["size"] == 5


def test_direct_backend_wrong_signature_rejected(admin):
    ts = int(__import__("time").time())
    resp = admin.get("/api/packages", headers={
        "X-Client": "cloud", "X-Timestamp": str(ts),
        "X-Nonce": uuid.uuid4().hex, "X-Sign": "deadbeef"})
    assert_err(resp, 401, 40102)


def test_cf_body_over_1mb_rejected(cf):
    big = json.dumps({"action": "packages", "payload": {"page": 1}, "pad": "x" * 1100000})
    resp = cf.post("/", raw_body=big.encode("utf-8"), timeout=15)
    assert_err(resp, 413, 40001)
