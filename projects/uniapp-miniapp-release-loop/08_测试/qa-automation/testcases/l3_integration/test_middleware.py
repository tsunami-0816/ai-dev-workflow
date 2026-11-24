#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""L3：中间件集成（真实 MySQL/Redis/RabbitMQ）。

降级说明：本机 16GB 内存且 Docker 中间件已常驻，未用 Testcontainers 另起容器，
按 step08 文档允许方式「docker-compose 起好中间件后手动连」执行，并在此记录。
"""
import json
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from api.booking_api import create_booking, my_bookings
from api.package_api import packages
from common.assert_util import assert_ok
from common.cf_util import NodeProc
from common.data_util import days_from_today, idem_key, mask, next_phone
from common.request_util import ApiClient
from common.wait_util import wait_until

pytestmark = pytest.mark.l3

CACHE_KEY = "ub:pkg:list"


def _stat(redis, key):
    return int(redis.info("stats").get(key, 0))


def test_cache_hit_ratio_above_80(redis, api):
    """C04：flush 后 20 次列表请求，keyspace hits/(hits+misses) > 80%。"""
    redis.delete(CACHE_KEY)
    hits_before, miss_before = _stat(redis, "keyspace_hits"), _stat(redis, "keyspace_misses")
    for _ in range(20):
        data = assert_ok(packages(api, 1, 10))
        assert data["total"] == 4
    hits = _stat(redis, "keyspace_hits") - hits_before
    misses = _stat(redis, "keyspace_misses") - miss_before
    ratio = hits / (hits + misses) if hits + misses else 0
    print(f"\nC04 cache hits={hits} misses={misses} ratio={ratio:.1%}")
    assert hits >= 18, f"20 次请求只命中 {hits} 次，缓存未生效"
    assert ratio >= 0.80, f"命中率 {ratio:.1%} < 80%"


def test_cache_single_flight_one_db_select(redis, mysql, cfg):
    """Q-012 回归：并发 10 请求 miss 只回源一次（MySQL Com_select 增量 ≤2）。"""
    redis.delete(CACHE_KEY)
    before = int(mysql.query("SHOW GLOBAL STATUS LIKE 'Com_select'")[0][1])

    def hit(_):
        client = ApiClient(cfg["base_url"], name="burst")
        resp = client.get("/api/packages?page=1&size=10")
        return resp.status == 200 and resp.body.get("code") == 0

    with ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(hit, range(10)))
    assert all(results)
    after = int(mysql.query("SHOW GLOBAL STATUS LIKE 'Com_select'")[0][1])
    delta = after - before
    print(f"\nQ-012 Com_select delta={delta}")
    assert delta <= 2, f"并发回源了 {delta} 次（单飞失效）"


def test_notify_log_payload_and_no_duplicate_on_replay(bookings, mysql, mq):
    resp, phone = bookings.create(package_id=2, book_date=days_from_today(11), slot="上午",
                                  remark="L3 MQ")
    booking_id = assert_ok(resp)["bookingId"]
    wait_until(lambda: mysql.scalar(f"SELECT COUNT(*) FROM notify_log WHERE booking_id={booking_id}") == "1",
               timeout=15, message="notify_log 未落库")
    payload = mysql.scalar(f"SELECT payload FROM notify_log WHERE booking_id={booking_id}")
    parsed = json.loads(payload)
    assert parsed["event"] == "booking.created"
    assert parsed["bookingId"] == booking_id
    assert "****" in parsed["contact"] and phone[-4:] in parsed["contact"]
    assert parsed["contact"] == mask(phone)

    # 重投同一事件：唯一键 (booking_id,event) 兜底，不翻倍
    mq.publish_raw(payload)
    time.sleep(3)
    assert mysql.scalar(f"SELECT COUNT(*) FROM notify_log WHERE booking_id={booking_id}") == "1"


def test_ten_bookings_all_notify_persisted(bookings, mysql):
    """C06：10 条预约消息，notify_log 落库 10 条（100%）。"""
    ids = []
    date = days_from_today(22)
    for i in range(10):
        resp, _ = bookings.create(package_id=1, book_date=date,
                                  slot=("上午", "下午", "晚间")[i % 3])
        ids.append(assert_ok(resp)["bookingId"])
    id_list = ",".join(str(i) for i in ids)
    wait_until(lambda: mysql.scalar(
        f"SELECT COUNT(*) FROM notify_log WHERE booking_id IN ({id_list})") == "10",
        timeout=20, message="10 条消息未在 20s 内全部落 notify_log")
    assert mysql.scalar(f"SELECT COUNT(*) FROM notify_log WHERE booking_id IN ({id_list})") == "10"


def test_invalid_message_goes_to_dlq(mq):
    before = mq.depth("booking.notify.dlq")
    mq.publish_raw("not-json")
    wait_until(lambda: mq.depth("booking.notify.dlq") >= before + 1, timeout=15, interval=1,
               message="非法消息未在 15s 内进入 DLQ")
    try:
        assert mq.depth("booking.notify.dlq") >= before + 1
    finally:
        mq.purge("booking.notify.dlq")


def test_idem_key_not_plaintext_and_ttl(bookings, redis):
    resp, phone = bookings.create(package_id=1, book_date=days_from_today(12), slot="下午")
    assert_ok(resp)
    key = idem_key(phone, days_from_today(12), "下午")
    assert redis.get(key) == "1"
    ttl = redis.ttl(key)
    assert 0 < ttl <= 600, f"幂等键 TTL={ttl}"


def test_get_openid_mock_paths(cfg):
    """L9：mock 微信 + 临时 getOpenid 实例，验成功/无效 code 两分支。"""
    with NodeProc("l3_mock_wx_8195", "test/mockWxServer.js", 8195,
                  {"MOCK_WX_PORT": "8195"}):
        with NodeProc("l3_openid_8194", "getOpenid/localServer.js", 8194,
                      {"OPENID_PORT": "8194", "MP_APPID": "wx_test_appid",
                       "MP_APPSECRET": "dummy-secret", "WX_API_BASE": "http://127.0.0.1:8195"}):
            client = ApiClient("http://127.0.0.1:8194", name="openid")
            good = client.post("/", {"code": "goodcode123456"})
            assert good.status == 200 and good.code() == 0, good.text[:300]
            assert good.data()["openid"].startswith("o_mock_")

            bad = client.post("/", {"code": "badcode123456"})
            assert bad.status == 400 and bad.code() == 40001, bad.text[:300]


def test_redis_isolation_other_user_list(api, api_b):
    """中间件层的用户隔离：B 的列表不含 A 的单（不依赖历史数据）。"""
    a = assert_ok(my_bookings(api, 1, 50))
    b = assert_ok(my_bookings(api_b, 1, 50))
    assert not ({x["id"] for x in a["list"]} & {x["id"] for x in b["list"]})
