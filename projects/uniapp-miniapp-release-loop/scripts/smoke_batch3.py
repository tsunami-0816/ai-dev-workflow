#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批次 3 冒烟（T-402 / T-403 / T-404 / T-501）
用法：python scripts/smoke_batch3.py
前置：后端 8092 已启动、MySQL 3308、RabbitMQ 5672/15672（admin/admin）
输出：控制台 + 05_代码/backend/evidence/smoke_batch3.txt
"""
import base64
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import date, timedelta
from pathlib import Path

BASE = "http://127.0.0.1:8092"
MGMT = "http://127.0.0.1:15672/api"
MQ_AUTH = "Basic " + base64.b64encode(b"admin:admin").decode()
MYSQL = ["mysql.exe", "--host=127.0.0.1", "--port=3308", "--user=root",
         "--password=123456", "--default-character-set=utf8mb4", "-N", "-B", "-D", "uniapp_booking"]
EVID = str(Path(__file__).resolve().parent.parent / "05_代码" / "backend" / "evidence" / "smoke_batch3.txt")
LINES = []
FAILS = []


def log(text=""):
    print(text)
    LINES.append(text)


def check(name, ok, detail=""):
    log(("PASS " if ok else "FAIL ") + name + ((" | " + detail) if detail else ""))
    if not ok:
        FAILS.append(name)


def http(method, path, body=None, token=None, raw=False):
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            text = resp.read().decode("utf-8")
            return resp.status, (text if raw else json.loads(text))
    except urllib.error.HTTPError as ex:
        text = ex.read().decode("utf-8")
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = text
        return ex.code, parsed


def sql(query):
    out = subprocess.run(MYSQL + ["-e", query], capture_output=True, text=True, encoding="utf-8")
    if out.returncode != 0:
        raise RuntimeError("mysql 失败: " + out.stderr.strip())
    return out.stdout.strip()


def mq(path):
    req = urllib.request.Request(MGMT + path, headers={"Authorization": MQ_AUTH})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def mq_publish(payload, props):
    data = json.dumps({"properties": props, "routing_key": "booking.created",
                       "payload": payload, "payload_encoding": "string"}).encode("utf-8")
    req = urllib.request.Request(MGMT + "/exchanges/%2F/booking.exchange/publish", data=data,
                                 headers={"Authorization": MQ_AUTH,
                                          "Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def queue_depth(name):
    q = mq("/queues/%2F/" + name)
    return q.get("messages", 0)


def queue_publish_count(name):
    """累计发布数（消费者实时消费时队列深度恒为 0，只能看 message_stats.publish）。"""
    q = mq("/queues/%2F/" + name)
    return q.get("message_stats", {}).get("publish", 0)


def login(account, password):
    st, body = http("POST", "/api/auth/login", {"account": account, "password": password})
    assert st == 200 and body["code"] == 0, f"登录失败 {account}: {st} {body}"
    return body["data"]["token"], body["data"]["userId"]


def main():
    today = date.today()
    d1 = (today + timedelta(days=1)).isoformat()
    d2 = (today + timedelta(days=2)).isoformat()
    d3 = (today + timedelta(days=3)).isoformat()
    log(f"=== 批次 3 冒烟 {time.strftime('%Y-%m-%d %H:%M:%S')} ===")
    log(f"base={BASE} today={today}")

    # 清理本次测试数据（幂等键残留由服务端自愈：键在行不在 → 清键重走）
    phones = [f"1390000{i:04d}" for i in range(1, 21)]
    sql("DELETE FROM notify_log WHERE booking_id IN (SELECT id FROM booking WHERE contact IN ("
        + ",".join(f"'{p}'" for p in phones) + "))")
    sql("DELETE FROM booking WHERE contact IN (" + ",".join(f"'{p}'" for p in phones) + ")")

    token_a, uid_a = login("demo", "welcome1")
    token_b, uid_b = login("demo2", "welcome1")
    log(f"loginA userId={uid_a} loginB userId={uid_b}")
    a_base = int(sql(f"SELECT COUNT(*) FROM booking WHERE user_id={uid_a}"))
    b_base = int(sql(f"SELECT COUNT(*) FROM booking WHERE user_id={uid_b}"))
    log(f"基线 booking 数 A={a_base} B={b_base}")

    # ---------- T-403 拓扑 ----------
    log("\n--- T-403 拓扑 ---")
    queues = [q["name"] for q in mq("/queues")]
    for name in ("booking.notify.queue", "booking.notify.dlq"):
        check("队列存在 " + name, name in queues)
    exchanges = [e["name"] for e in mq("/exchanges")]
    for name in ("booking.exchange", "booking.dlx"):
        check("交换机存在 " + name, name in exchanges)
    before = queue_publish_count("booking.notify.queue")

    # ---------- T-402 幂等 ----------
    log("\n--- T-402 幂等（同人同日同时段 3 次） ---")
    req = {"packageId": 1, "bookDate": d1, "slot": "上午", "contact": phones[0], "remark": "T-402 幂等"}
    ids, dups = [], []
    for i in range(3):
        st, body = http("POST", "/api/bookings", req, token_a)
        log(f"req{i + 1} HTTP={st} {json.dumps(body, ensure_ascii=False)}")
        check(f"req{i + 1} code=0", st == 200 and body.get("code") == 0)
        ids.append(body["data"]["bookingId"])
        dups.append(body["data"]["duplicated"])
    check("3 次同一 bookingId", len(set(ids)) == 1, str(ids))
    check("首单 duplicated=false", dups[0] is False, str(dups))
    check("第 2/3 次 duplicated=true", dups[1] is True and dups[2] is True, str(dups))
    cnt = sql(f"SELECT COUNT(*) FROM booking WHERE contact='{phones[0]}' AND book_date='{d1}' AND slot='上午'")
    check("DB 计数=1", cnt == "1", "count=" + cnt)
    # Management API 统计按 5s 粒度刷新，读差值前等一个刷新周期
    time.sleep(6)
    after = queue_publish_count("booking.notify.queue")
    log(f"notify.queue 累计发布 before={before} after={after}（深度={queue_depth('booking.notify.queue')}）")
    check("提交 1 单消息数 +1（重复提交不再发消息）", after - before == 1, f"delta={after - before}")
    booking_id = ids[0]
    time.sleep(1)
    nl = sql(f"SELECT COUNT(*) FROM notify_log WHERE booking_id={booking_id}")
    check("T-404 首单 notify_log=1", nl == "1", "count=" + nl)

    # ---------- 参数校验 ----------
    log("\n--- 参数校验 ---")
    st, body = http("POST", "/api/bookings", {"packageId": 1, "bookDate": "2020-01-01",
                                              "slot": "上午", "contact": phones[1]}, token_a)
    check("过去日期 40002", st == 400 and body.get("code") == 40002, f"{st} {body}")
    st, body = http("POST", "/api/bookings", {"packageId": 1, "bookDate": (today + timedelta(days=60)).isoformat(),
                                              "slot": "上午", "contact": phones[1]}, token_a)
    check("超 30 天 40002", st == 400 and body.get("code") == 40002, f"{st} {body}")
    st, body = http("POST", "/api/bookings", {"packageId": 999, "bookDate": d1,
                                              "slot": "上午", "contact": phones[1]}, token_a)
    check("套餐不存在 40401", st == 404 and body.get("code") == 40401, f"{st} {body}")
    st, body = http("POST", "/api/bookings", {"packageId": 1, "bookDate": d1,
                                              "slot": "凌晨", "contact": phones[1]}, token_a)
    check("非法时段 40001", st == 400 and body.get("code") == 40001, f"{st} {body}")
    st, body = http("POST", "/api/bookings", {"packageId": 1, "bookDate": d1,
                                              "slot": "上午", "contact": "123"}, token_a)
    check("手机号非法 40001", st == 400 and body.get("code") == 40001, f"{st} {body}")
    st, body = http("POST", "/api/bookings", {"packageId": 1, "bookDate": d1,
                                              "slot": "上午", "contact": phones[1]})
    check("无 token 40101", st == 401 and body.get("code") == 40101, f"{st} {body}")
    st, body = http("GET", "/api/no-such-path")
    check("未知路径 404 + 40400", st == 404 and body.get("code") == 40400, f"{st} {body}")

    # ---------- T-404 10 单 → 10 条 ----------
    log("\n--- T-404 10 单 → notify_log=10 ---")
    created = []
    for i in range(10):
        st, body = http("POST", "/api/bookings", {"packageId": 2, "bookDate": d2,
                                                  "slot": "下午", "contact": phones[2 + i]}, token_a)
        if st == 200:
            created.append(body["data"]["bookingId"])
    check("10 单全部创建成功", len(created) == 10, f"created={len(created)}")
    deadline = time.time() + 15
    count = "0"
    while time.time() < deadline:
        ids_sql = ",".join(str(x) for x in created)
        count = sql(f"SELECT COUNT(*) FROM notify_log WHERE booking_id IN ({ids_sql})")
        if count == "10":
            break
        time.sleep(1)
    check("notify_log=10", count == "10", "count=" + count)

    # 重复投递不翻倍：手工重投首单同事件
    log("\n--- 重复投递幂等 ---")
    replay = json.dumps({"event": "booking.created", "bookingId": created[0], "userId": uid_a,
                         "packageId": 2, "bookDate": d2, "slot": "下午",
                         "contact": phones[2][:3] + "****" + phones[2][-4:],
                         "createdAt": time.strftime("%Y-%m-%dT%H:%M:%S")}, ensure_ascii=False)
    mq_publish(replay, {"content_type": "application/json",
                        "__TypeId__": "com.uniapp.booking.mq.BookingCreatedEvent"})
    time.sleep(2)
    total = sql(f"SELECT COUNT(*) FROM notify_log WHERE booking_id={created[0]}")
    check("重复投递不翻倍（仍为 1）", total == "1", "count=" + total)

    # ---------- T-501 我的预约 ----------
    log("\n--- T-501 我的预约 ---")
    st, body = http("GET", "/api/bookings?page=1&size=20", None, token_a)
    check("A 列表 code=0", st == 200 and body.get("code") == 0, f"{st}")
    a_total = body["data"]["total"]
    check("A total=基线+11", a_total == a_base + 11, f"total={a_total} base={a_base}")
    st, body2 = http("GET", f"/api/bookings?page=1&size=20&userId={uid_a}", None, token_b)
    b_list = body2["data"]["list"]
    check("B 用伪造 userId=A 仍只见自己的单", all(x["id"] not in created for x in b_list) and
          body2["data"]["total"] == b_base, f"B total={body2['data']['total']} base={b_base}")
    st, body = http("GET", "/api/bookings?page=2&size=5", None, token_a)
    check("A 第 2 页 5 条", st == 200 and len(body["data"]["list"]) == 5, f"len={len(body['data']['list'])}")
    if body["data"]["list"]:
        log("列表首条: " + json.dumps(body["data"]["list"][0], ensure_ascii=False))
        check("手机号已脱敏", "****" in body["data"]["list"][0]["contactMasked"])
    st, body = http("GET", "/api/bookings", None, None)
    check("无 token 40101", st == 401 and body.get("code") == 40101, f"{st}")

    # ---------- DLQ：非法消息重试 3 次后入死信 ----------
    log("\n--- DLQ 验证（非法消息） ---")
    before_dlq = queue_depth("booking.notify.dlq")
    mq_publish("not-json", {"content_type": "application/json",
                            "__TypeId__": "com.uniapp.booking.mq.BookingCreatedEvent"})
    time.sleep(8)
    after_dlq = queue_depth("booking.notify.dlq")
    log(f"dlq before={before_dlq} after={after_dlq}")
    check("非法消息入 DLQ", after_dlq - before_dlq == 1, f"delta={after_dlq - before_dlq}")

    log("\n=== 结果：" + ("全部通过" if not FAILS else f"{len(FAILS)} 项失败 -> {FAILS}") + " ===")
    with open(EVID, "w", encoding="utf-8") as f:
        f.write("\n".join(LINES) + "\n")
    return 0 if not FAILS else 1


if __name__ == "__main__":
    sys.exit(main())
