#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
T-206 云函数冒烟（apiProxy / getOpenid）
用法：python scripts/smoke_cf.py
前置：后端 8092 已启动（health=UP）；8093 可由脚本自动拉起
说明：测试专用临时实例（8094/8095/8096/8097/8098）由本脚本起停，不占正式端口表
输出：控制台 + 05_代码/cloud-functions/evidence/smoke_cf.txt
"""
import json
import os
import random
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import date, timedelta
from pathlib import Path

CF_ROOT = Path(__file__).resolve().parent.parent / "05_代码" / "cloud-functions"
EVID_DIR = CF_ROOT / "evidence"
EVID = EVID_DIR / "smoke_cf.txt"
BACKEND = "http://127.0.0.1:8092"
PROXY = "http://127.0.0.1:8093"

LINES = []
FAILS = []
SPAWNED = []
FLAGS = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def log(text=""):
    print(text)
    LINES.append(text)


def check(name, ok, detail=""):
    log(("PASS " if ok else "FAIL ") + name + ((" | " + detail) if detail else ""))
    if not ok:
        FAILS.append(name)


def section(title):
    log("")
    log("== " + title + " ==")


def port_open(port):
    s = socket.socket()
    s.settimeout(0.5)
    try:
        return s.connect_ex(("127.0.0.1", port)) == 0
    finally:
        s.close()


def wait_port(port, timeout=12.0):
    end = time.time() + timeout
    while time.time() < end:
        if port_open(port):
            return True
        time.sleep(0.3)
    return False


def http_json(url, method="GET", payload=None, raw=None, headers=None, timeout=20):
    if raw is not None:
        data = raw
    elif payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    else:
        data = None
    h = {"Content-Type": "application/json; charset=utf-8"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            text = resp.read().decode("utf-8")
            return resp.status, json.loads(text)
    except urllib.error.HTTPError as ex:
        text = ex.read().decode("utf-8")
        try:
            return ex.code, json.loads(text)
        except json.JSONDecodeError:
            return ex.code, {"raw": text}
    except Exception as ex:  # 连接拒绝 / 超时
        return 0, {"error": str(ex)}


class NodeProc:
    """测试专用 Node 实例：独立端口 + 独立环境变量 + 独立日志。"""

    def __init__(self, name, script, port, env_extra=None):
        self.name = name
        self.script = script
        self.port = port
        self.env_extra = env_extra or {}
        self.proc = None
        self.log_path = None

    def start(self):
        env = dict(os.environ)
        env.update(self.env_extra)
        self.log_path = EVID_DIR / (self.name + ".log")
        fh = open(self.log_path, "wb")
        self.proc = subprocess.Popen(
            ["node", "--max-old-space-size=256", self.script],
            cwd=str(CF_ROOT),
            env=env,
            stdout=fh,
            stderr=subprocess.STDOUT,
            creationflags=FLAGS,
        )
        fh.close()
        SPAWNED.append(self)
        if not wait_port(self.port):
            log("  [warn] %s 端口 %d 未在 12s 内就绪（见 %s）" % (self.name, self.port, self.log_path.name))
            return False
        return True

    def stop(self):
        if not self.proc:
            return
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self.proc = None


def cleanup():
    for p in reversed(SPAWNED):
        try:
            p.stop()
        except Exception:
            pass


def main():
    if not EVID_DIR.exists():
        EVID_DIR.mkdir(parents=True, exist_ok=True)
    log("T-206 云函数冒烟  %s" % time.strftime("%Y-%m-%d %H:%M:%S"))
    log("CF_ROOT = %s" % CF_ROOT)

    section("0. 前置")
    status, body = http_json(BACKEND + "/actuator/health")
    if status != 200 or body.get("status") != "UP":
        log("❌ 后端 8092 health 非 UP（status=%s body=%s），先跑 scripts\\start_all.ps1" % (status, body))
        return 2
    check("后端 /actuator/health = UP", True, "HTTP 200")

    section("1. apiProxy 8093")
    if port_open(8093):
        log("  8093 已在监听，复用（不重复拉起）")
        proxy_owned = False
    else:
        p = NodeProc("cf_8093", "apiProxy/localServer.js", 8093,
                     {"CF_PORT": "8093", "CF_MODE": "http", "CF_BACKEND_BASE": BACKEND})
        proxy_owned = p.start()
        if not proxy_owned:
            cleanup()
            return 2

    status, body = http_json(PROXY + "/healthz")
    check("GET /healthz = UP", status == 200 and body.get("status") == "UP", "HTTP %s" % status)

    status, body = http_json(PROXY + "/healthz?probe=1")
    probe = body.get("backendProbe") or {}
    check("健康探针（云函数→后端签名链路）",
          status == 200 and probe.get("code") == 0,
          "code=%s elapsedMs=%s" % (probe.get("code"), probe.get("elapsedMs")))

    status, body = http_json(PROXY + "/", "POST", {"action": "packages", "payload": {"page": 1, "size": 2}})
    items = (body.get("data") or {}).get("list") or []
    check("packages 转发（size=2）", status == 200 and body.get("code") == 0 and len(items) == 2,
          "HTTP %s code=%s list=%d" % (status, body.get("code"), len(items)))

    status, body = http_json(PROXY + "/", "POST", {"action": "packageDetail", "payload": {"id": 2}})
    check("packageDetail 转发（id=2）",
          status == 200 and body.get("code") == 0 and (body.get("data") or {}).get("id") == 2,
          "HTTP %s code=%s" % (status, body.get("code")))

    status, body = http_json(PROXY + "/", "POST", {"action": "no-such-action", "payload": {}})
    check("未知 action → 400/40001", status == 400 and body.get("code") == 40001,
          "HTTP %s code=%s msg=%s" % (status, body.get("code"), body.get("msg")))

    status, body = http_json(PROXY + "/", "POST",
                             {"action": "createBooking",
                              "payload": {"packageId": 1, "bookDate": "2026-12-01", "slot": "下午",
                                          "contact": "13800138000", "userId": 1}, "token": "x.y.z"})
    check("未知字段 userId 被拦 → 40001", status == 400 and body.get("code") == 40001,
          "HTTP %s code=%s msg=%s" % (status, body.get("code"), body.get("msg")))

    # 登录（拿 token）
    status, body = http_json(PROXY + "/", "POST",
                             {"action": "login", "payload": {"account": "demo", "password": "welcome1"}})
    token = (body.get("data") or {}).get("token")
    check("login 转发（demo/welcome1）", status == 200 and body.get("code") == 0 and bool(token),
          "HTTP %s userId=%s" % (status, (body.get("data") or {}).get("userId")))

    section("2. 一单可通（写链路穿过云函数）")
    phone = "1380013" + str(random.randint(1000, 9999))
    book_date = (date.today() + timedelta(days=3)).isoformat()
    booking = {"action": "createBooking",
               "payload": {"packageId": 1, "bookDate": book_date, "slot": "下午",
                           "contact": phone, "remark": "T-206 冒烟"},
               "token": token}
    status, body = http_json(PROXY + "/", "POST", booking)
    first_id = (body.get("data") or {}).get("bookingId")
    check("createBooking 首单", status == 200 and body.get("code") == 0 and bool(first_id),
          "HTTP %s code=%s bookingId=%s" % (status, body.get("code"), first_id))

    status, body = http_json(PROXY + "/", "POST", booking)
    data2 = body.get("data") or {}
    check("createBooking 重发（幂等）",
          status == 200 and body.get("code") == 0 and data2.get("duplicated") is True and data2.get("bookingId") == first_id,
          "bookingId=%s duplicated=%s" % (data2.get("bookingId"), data2.get("duplicated")))

    status, body = http_json(PROXY + "/", "POST",
                             {"action": "myBookings", "payload": {"page": 1, "size": 10}, "token": token})
    ids = [x.get("id") for x in ((body.get("data") or {}).get("list") or [])]
    check("myBookings 可见本单", status == 200 and body.get("code") == 0 and first_id in ids,
          "total=%s 命中=%s" % ((body.get("data") or {}).get("total"), first_id in ids))

    section("3. 签名真实性（防伪对照）")
    ts = str(int(time.time()))
    _, body = http_json(BACKEND + "/api/packages", "GET", headers={
        "X-Client": "cloud", "X-Timestamp": ts,
        "X-Nonce": uuid.uuid4().hex, "X-Sign": "deadbeef"})
    check("直连后端 + 错误签名 → 401/40102", body.get("code") == 40102,
          "code=%s" % body.get("code"))

    # 错密钥实例：若云函数不签名或密钥不一致，后端必然 40102 → 反证 8093 的调用确实带对了签名
    wrong = NodeProc("cf_wrong_secret", "apiProxy/localServer.js", 8097, {
        "CF_PORT": "8097", "CF_BACKEND_BASE": BACKEND,
        "APP_SECRET": "definitely-wrong-secret-for-test"})
    if wrong.start():
        status, body = http_json("http://127.0.0.1:8097/", "POST",
                                 {"action": "packages", "payload": {}}, timeout=10)
        check("云函数使用错误 APP_SECRET → 401/40102", status == 401 and body.get("code") == 40102,
              "HTTP %s code=%s" % (status, body.get("code")))
    else:
        check("云函数使用错误 APP_SECRET → 401/40102", False, "实例未就绪")

    section("4. 超时降级（3s 超时 + 重试 1 次 → 50002）")
    hang = NodeProc("cf_hang_backend", "test/hangServer.js", 8096, {"HANG_PORT": "8096"})
    if hang.start():
        slow = NodeProc("cf_slow_proxy", "apiProxy/localServer.js", 8098, {
            "CF_PORT": "8098", "CF_BACKEND_BASE": "http://127.0.0.1:8096",
            "CF_TIMEOUT_MS": "3000", "CF_RETRY": "1"})
        if slow.start():
            t0 = time.time()
            status, body = http_json("http://127.0.0.1:8098/", "POST",
                                     {"action": "packages", "payload": {}}, timeout=30)
            wall = int((time.time() - t0) * 1000)
            check("后端挂起 → 504/50002「网络不稳定，请重试」",
                  status == 504 and body.get("code") == 50002 and "网络不稳定" in (body.get("msg") or ""),
                  "HTTP %s code=%s wall=%dms elapsedMs=%s" % (status, body.get("code"), wall, body.get("elapsedMs")))
            check("重试确实发生（总耗时 ≥ 5s）", wall >= 5000 and body.get("elapsedMs", 0) >= 5000,
                  "wall=%dms" % wall)
        else:
            check("后端挂起 → 504/50002", False, "slow proxy 未就绪")
    else:
        check("后端挂起 → 504/50002", False, "hang server 未就绪")

    section("5. 请求体上限 1MB")
    big = json.dumps({"action": "packages", "payload": {"page": 1}, "pad": "x" * 1100000}).encode("utf-8")
    status, body = http_json(PROXY + "/", "POST", raw=big, timeout=10)
    check("1.1MB 请求体 → 413/40001", status == 413 and body.get("code") == 40001,
          "HTTP %s code=%s msg=%s" % (status, body.get("code"), body.get("msg")))

    section("6. getOpenid")
    no_secret = NodeProc("openid_no_secret", "getOpenid/localServer.js", 8094, {
        "OPENID_PORT": "8094", "MP_APPID": "wx_test_appid", "MP_APPSECRET": ""})
    if no_secret.start():
        status, body = http_json("http://127.0.0.1:8094/", "POST", {"code": "goodcode123456"}, timeout=10)
        check("缺 MP_APPSECRET → 50001 且提示未配置",
              status == 500 and body.get("code") == 50001 and "MP_APPSECRET" in (body.get("msg") or ""),
              "HTTP %s msg=%s" % (status, body.get("msg")))
        no_secret.stop()
        time.sleep(0.5)

    mock = NodeProc("mock_wx_8095", "test/mockWxServer.js", 8095, {"MOCK_WX_PORT": "8095"})
    if mock.start():
        openid = NodeProc("openid_mock", "getOpenid/localServer.js", 8094, {
            "OPENID_PORT": "8094", "MP_APPID": "wx_test_appid", "MP_APPSECRET": "dummy-secret",
            "WX_API_BASE": "http://127.0.0.1:8095"})
        if openid.start():
            status, body = http_json("http://127.0.0.1:8094/", "POST", {"code": "goodcode123456"}, timeout=10)
            got = (body.get("data") or {}).get("openid") or ""
            check("code2session 成功路径（mock 微信）",
                  status == 200 and body.get("code") == 0 and got.startswith("o_mock_"),
                  "HTTP %s openid=%s" % (status, got))

            status, body = http_json("http://127.0.0.1:8094/", "POST", {"code": "badcode123456"}, timeout=10)
            check("无效 code → 400/40001", status == 400 and body.get("code") == 40001,
                  "HTTP %s msg=%s" % (status, body.get("msg")))
        else:
            check("code2session 成功路径（mock 微信）", False, "getOpenid 未就绪")
    else:
        check("code2session 成功路径（mock 微信）", False, "mock 微信未就绪")

    log("")
    log("== 结果 ==")

    return 0 if not FAILS else 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    code = 0
    try:
        code = main()
    finally:
        cleanup()
        passed = len([x for x in LINES if x.startswith("PASS ")])
        failed = len([x for x in LINES if x.startswith("FAIL ")])
        LINES.append("")
        LINES.append("PASS = %d, FAIL = %d, exit = %d" % (passed, failed, code))
        if failed or code != 0:
            LINES.append("FAILED: " + ", ".join(FAILS))
        EVID.write_text("\n".join(LINES) + "\n", encoding="utf-8")
        log("\n证据已写入 %s" % EVID)
    sys.exit(code)
