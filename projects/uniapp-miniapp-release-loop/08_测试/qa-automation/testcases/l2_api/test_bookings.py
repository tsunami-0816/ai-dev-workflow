#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""L2：预约写链路四象限 + 我的列表（按用户隔离、分页、脱敏、幂等）。"""
import time

import pytest

from api.booking_api import create_booking, my_bookings
from common.assert_util import assert_err, assert_ok
from common.data_util import days_from_today, idem_key, mask, next_phone
from common.wait_util import wait_until

pytestmark = pytest.mark.l2


def test_create_booking_persists_and_sets_idem_key(bookings, mysql, redis):
    resp, phone = bookings.create(package_id=1, book_date=days_from_today(3), slot="上午",
                                  remark="L2 正向")
    data = assert_ok(resp)
    assert data["status"] == 0
    assert data["duplicated"] is False
    booking_id = data["bookingId"]
    assert booking_id > 0

    row = mysql.query(f"SELECT user_id,package_id,book_date,slot,contact,status FROM booking "
                      f"WHERE id={booking_id}")
    assert len(row) == 1
    assert row[0][3] == "上午" and row[0][4] == phone and row[0][5] == "0"

    key = idem_key(phone, days_from_today(3), "上午")
    assert redis.get(key) == "1"
    assert 0 < redis.ttl(key) <= 600


def test_idempotent_three_submits_one_row_and_one_message(bookings, mysql, mq):
    date, slot, phone = days_from_today(4), "下午", next_phone()
    before_publish = mq.publish_count("booking.notify.queue")
    ids, flags = [], []
    for _ in range(3):
        resp, _ = bookings.create(package_id=2, book_date=date, slot=slot, contact=phone)
        data = assert_ok(resp)
        ids.append(data["bookingId"])
        flags.append(data["duplicated"])
    assert len(set(ids)) == 1, ids
    assert flags == [False, True, True]

    count = mysql.scalar(f"SELECT COUNT(*) FROM booking WHERE contact='{phone}' "
                         f"AND book_date='{date}' AND slot='{slot}'")
    assert count == "1"

    notify = wait_until(
        lambda: mysql.scalar(f"SELECT COUNT(*) FROM notify_log WHERE booking_id={ids[0]}") == "1",
        timeout=15, message="notify_log 未在 15s 内落 1 条")
    assert notify

    def publish_grew():
        return mq.publish_count("booking.notify.queue") - before_publish >= 1

    wait_until(publish_grew, timeout=15, interval=1,
               message="重复提交不应重复发消息：queue publish 未 +1")


def test_cross_account_same_phone_date_slot_rejected(bookings, api_b):
    resp, phone = bookings.create(package_id=1, book_date=days_from_today(5), slot="晚间")
    assert_ok(resp)
    other = create_booking(api_b, 1, days_from_today(5), "晚间", phone)
    assert_err(other, 400, 40001)
    assert "已有预约" in (other.msg() or "")


def test_my_list_contains_new_booking(bookings, api):
    resp, phone = bookings.create(package_id=3, book_date=days_from_today(6), slot="上午")
    booking_id = assert_ok(resp)["bookingId"]
    data = assert_ok(my_bookings(api, 1, 20))
    assert booking_id in [x["id"] for x in data["list"]]
    item = next(x for x in data["list"] if x["id"] == booking_id)
    assert item["contactMasked"] == mask(phone)
    assert item["statusText"] == "待确认"
    assert item["packageTitle"] == "情侣纪实"


def test_my_list_pagination(bookings, api):
    for slot in ("上午", "下午", "晚间"):
        assert_ok(bookings.create(package_id=1, book_date=days_from_today(7), slot=slot)[0])
    page1 = assert_ok(my_bookings(api, 1, 2))
    page2 = assert_ok(my_bookings(api, 2, 2))
    assert page1["page"] == 1 and page2["page"] == 2
    assert len(page1["list"]) == 2
    assert len(page2["list"]) >= 1
    assert page1["total"] >= 3


def test_my_list_page_and_size_clamped(api):
    data = assert_ok(my_bookings(api, 0, 999))
    assert data["page"] == 1
    assert data["size"] == 10


def test_forged_userid_query_ignored(bookings, api_b, account):
    resp, _ = bookings.create(package_id=1, book_date=days_from_today(8), slot="上午")
    demo_booking = assert_ok(resp)["bookingId"]
    data = assert_ok(my_bookings(api_b, 1, 20, extra_query=f"userId={account['user_id']}"))
    assert demo_booking not in [x["id"] for x in data["list"]]


def test_unauthorized_booking_list(admin):
    assert_err(my_bookings(admin), 401, 40101)


def test_unauthorized_booking_create(admin):
    assert_err(create_booking(admin, 1, days_from_today(3), "上午", next_phone()), 401, 40101)


@pytest.mark.parametrize("field,value,status,code", [
    ("packageId", None, 400, 40001),
    ("bookDate", "2026/12/01", 400, 40001),
    ("bookDate", "", 400, 40001),
    ("slot", "凌晨", 400, 40001),
    ("slot", "", 400, 40001),
    ("contact", "123", 400, 40001),
    ("contact", "23800138000", 400, 40001),
])
def test_booking_field_validation(api, field, value, status, code):
    body = {"packageId": 1, "bookDate": days_from_today(3), "slot": "上午",
            "contact": next_phone(), field: value}
    resp = api.post("/api/bookings", body)
    assert_err(resp, status, code)


def test_booking_past_date_rejected(api):
    resp = create_booking(api, 1, days_from_today(-1), "上午", next_phone())
    assert_err(resp, 400, 40002)


def test_booking_over_30_days_rejected(api):
    resp = create_booking(api, 1, days_from_today(31), "上午", next_phone())
    assert_err(resp, 400, 40002)


def test_booking_package_not_found(api):
    resp = create_booking(api, 999, days_from_today(3), "上午", next_phone())
    assert_err(resp, 404, 40401)


def test_remark_255_chars_accepted(bookings):
    resp, _ = bookings.create(package_id=1, book_date=days_from_today(9), slot="下午",
                              remark="注" * 255)
    assert_ok(resp)


def test_remark_256_chars_rejected(api):
    resp = create_booking(api, 1, days_from_today(9), "晚间", next_phone(), remark="注" * 256)
    assert_err(resp, 400, 40001)


def test_unknown_path_40400(admin):
    assert_err(admin.get("/api/no-such-path"), 404, 40400)
