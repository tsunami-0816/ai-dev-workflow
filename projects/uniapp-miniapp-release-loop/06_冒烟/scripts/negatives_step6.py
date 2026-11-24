# -*- coding: utf-8 -*-
"""第 6 步负向走查（N1 幂等 / N2 跨账号 / N4 无 token / N5 未知路径）→ 06_冒烟/evidence/step6_negatives.json"""
import json
import urllib.error
import urllib.request
from datetime import date, timedelta
from pathlib import Path

BASE = "http://127.0.0.1:8092"
OUT = Path(__file__).resolve().parent.parent / "evidence" / "step6_negatives.json"


def call(method, path, body=None, token=None):
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    headers = {}
    if data:
        headers["Content-Type"] = "application/json; charset=utf-8"
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        txt = e.read().decode("utf-8")
        try:
            return e.code, json.loads(txt)
        except json.JSONDecodeError:
            return e.code, txt


def login(account):
    st, b = call("POST", "/api/auth/login", {"account": account, "password": "welcome1"})
    return b["data"]["token"]


def main():
    d = (date.today() + timedelta(days=1)).isoformat()
    ta, tb = login("demo"), login("demo2")
    body = {"packageId": 3, "bookDate": d, "slot": "上午", "contact": "13811110001", "remark": "N1/N2 走查"}
    res = {}

    s1, b1 = call("POST", "/api/bookings", body, ta)
    s2, b2 = call("POST", "/api/bookings", body, ta)
    res["N1"] = {
        "first": {"http": s1, "id": b1["data"]["bookingId"], "duplicated": b1["data"]["duplicated"]},
        "second": {"http": s2, "id": b2["data"]["bookingId"], "duplicated": b2["data"]["duplicated"]},
        "pass": b1["data"]["bookingId"] == b2["data"]["bookingId"] and b1["data"]["duplicated"] is False and b2["data"]["duplicated"] is True,
    }

    s3, b3 = call("POST", "/api/bookings", body, tb)
    res["N2"] = {"http": s3, "code": b3.get("code"), "msg": b3.get("msg"), "hasData": bool(b3.get("data")),
                 "pass": s3 == 400 and b3.get("code") == 40001 and not b3.get("data")}

    s4, b4 = call("GET", "/api/bookings")
    res["N4"] = {"http": s4, "code": b4.get("code"), "pass": s4 == 401 and b4.get("code") == 40101}

    s5, b5 = call("GET", "/api/no-such-path")
    res["N5"] = {"http": s5, "code": b5.get("code"), "pass": s5 == 404 and b5.get("code") == 40400}

    res["allPass"] = all(res[k]["pass"] for k in ("N1", "N2", "N4", "N5"))
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=2))
    raise SystemExit(0 if res["allPass"] else 1)


if __name__ == "__main__":
    main()
