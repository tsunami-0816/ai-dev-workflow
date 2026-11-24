#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试夹具：环境探活、双账号客户端、MySQL/Redis/MQ、自造自清预约数据。

规则：
- 每条用例自己造数据、自己清理（规则 3）；
- 断言前刷新快照（这里用独立 SQL 连接读库，天然是最新快照，规则 6）；
- 不依赖库里已有业务数据（规则 7）。
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common.account_util import ensure_account  # noqa: E402
from common.config_loader import load_config  # noqa: E402
from common.data_util import idem_key, next_phone  # noqa: E402
from common.mq_util import Mq  # noqa: E402
from common.redis_util import Redis  # noqa: E402
from common.request_util import ApiClient  # noqa: E402
from common.sql_util import Mysql  # noqa: E402


@pytest.fixture(scope="session")
def cfg():
    return load_config()


@pytest.fixture(scope="session", autouse=True)
def env_guard(cfg):
    """后端与云函数必须先起；起不来是环境阻断，直接 fail 并说明，不用 skip 掩盖。"""
    admin = ApiClient(cfg["base_url"], name="env")
    resp = admin.get("/actuator/health", timeout=5)
    assert resp.status == 200 and resp.body.get("status") == "UP", \
        f"后端 8092 health 非 UP: {resp.status} {resp.text[:200]}（先跑 scripts/start_all.ps1）"
    assert cfg["mysql"]["port"] == 3307, "第 8 步基线库必须是 3307（Q-024）"
    return True


@pytest.fixture(scope="session")
def admin(cfg):
    return ApiClient(cfg["base_url"], name="admin")


@pytest.fixture(scope="session")
def cf(cfg):
    return ApiClient(cfg["cf_url"], name="cf")


@pytest.fixture(scope="session")
def account(cfg, mysql):
    data = _login_or_seed(cfg, mysql, "demo", "演示用户A")
    return {"token": data[0], "user_id": data[1]}


@pytest.fixture(scope="session")
def account_b(cfg, mysql):
    data = _login_or_seed(cfg, mysql, "demo2", "演示用户B")
    return {"token": data[0], "user_id": data[1]}


def _login_or_seed(cfg, mysql, key, nickname):
    """登录失败时按后端同参数 PBKDF2 补种账号再登录（不依赖人工准备口令）。"""
    account = cfg["accounts"][key]["account"]
    password = cfg["accounts"][key]["password"]
    client = ApiClient(cfg["base_url"], timeout=20, name="login")
    resp = client.post("/api/auth/login", {"account": account, "password": password})
    if not (resp.status == 200 and resp.code() == 0):
        ensure_account(mysql, account, password, nickname)
        resp = client.post("/api/auth/login", {"account": account, "password": password})
    assert resp.status == 200 and resp.code() == 0, \
        f"登录失败（含自动补种）{resp.status} {resp.text[:200]}"
    data = resp.data()
    return data["token"], data["userId"]


@pytest.fixture(scope="session")
def api(cfg, account):
    return ApiClient(cfg["base_url"], token=account["token"], name="demo")


@pytest.fixture(scope="session")
def api_b(cfg, account_b):
    return ApiClient(cfg["base_url"], token=account_b["token"], name="demo2")


@pytest.fixture(scope="session")
def mysql(cfg):
    return Mysql(cfg["mysql"])


@pytest.fixture(scope="session")
def redis(cfg):
    client = Redis(cfg["redis"]["host"], cfg["redis"]["port"])
    assert client.ping(), "Redis PING 失败"
    return client


@pytest.fixture(scope="session")
def mq(cfg):
    return Mq(cfg["mq"])


class BookingFactory:
    """造预约并登记清理：按 bookingId 删 notify_log/booking，按 contact/date/slot 删幂等键。"""

    def __init__(self, api, mysql, redis):
        self.api = api
        self.mysql = mysql
        self.redis = redis
        self.created = []  # (booking_id, contact, book_date, slot)

    def create(self, package_id=1, book_date=None, slot="上午", contact=None, remark=None):
        from common.data_util import days_from_today
        from api.booking_api import create_booking

        contact = contact or next_phone()
        book_date = book_date or days_from_today(3)
        resp = create_booking(self.api, package_id, book_date, slot, contact, remark)
        if resp.status == 200 and resp.code() == 0:
            self.created.append((resp.data()["bookingId"], contact, book_date, slot))
        return resp, contact

    def cleanup(self):
        ids = [x[0] for x in self.created]
        if ids:
            id_list = ",".join(str(i) for i in ids)
            self.mysql.execute(f"DELETE FROM notify_log WHERE booking_id IN ({id_list})")
            self.mysql.execute(f"DELETE FROM booking WHERE id IN ({id_list})")
        for _, contact, book_date, slot in self.created:
            self.redis.delete(idem_key(contact, book_date, slot))
        self.created.clear()


@pytest.fixture
def bookings(api, mysql, redis):
    factory = BookingFactory(api, mysql, redis)
    yield factory
    factory.cleanup()
