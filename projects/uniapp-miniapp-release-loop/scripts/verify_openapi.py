#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
T-704 契约结构校验：5 路径 / 6 操作、4 个签名头已声明、无 /api 之外的路径。
用法：python scripts/verify_openapi.py 06.5_契约/openapi.json
"""
import json
import sys
from pathlib import Path

EXPECT_PATHS = {
    "/api/auth/login",
    "/api/auth/logout",
    "/api/packages",
    "/api/packages/{id}",
    "/api/bookings",
}
EXPECT_HEADERS = {"X-Client", "X-Sign", "X-Timestamp", "X-Nonce"}
FAILS = []


def main():
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "06.5_契约/openapi.json")
    doc = json.loads(path.read_text(encoding="utf-8"))
    paths = doc.get("paths", {})
    got = set(paths)
    print(f"paths={len(got)}: {sorted(got)}")
    if got != EXPECT_PATHS:
        FAILS.append(f"路径集合不一致: 多={sorted(got - EXPECT_PATHS)} 少={sorted(EXPECT_PATHS - got)}")

    methods = {"get", "post", "put", "delete", "patch"}
    ops = [(p, m) for p in paths for m in paths[p] if m in methods]
    print(f"operations={len(ops)}")
    if len(ops) != 6:
        FAILS.append(f"操作数={len(ops)}，应为 6")

    for p, q in paths.items():
        if not p.startswith("/api/"):
            FAILS.append(f"出现非业务路径: {p}")
        for method, op in q.items():
            if method not in methods:
                continue
            names = {x.get("name") for x in op.get("parameters", []) if x.get("in") == "header"}
            missing = EXPECT_HEADERS - names
            if missing:
                FAILS.append(f"{method.upper()} {p} 未声明头: {sorted(missing)}")

    schemes = doc.get("components", {}).get("securitySchemes", {})
    print(f"securitySchemes={sorted(schemes)}")
    if "bearerAuth" not in schemes:
        FAILS.append("缺少 bearerAuth 安全方案")

    if FAILS:
        print("\n".join("FAIL " + f for f in FAILS))
        print(f"结果：{len(FAILS)} 项失败")
        return 1
    print("结果：全部通过（路径/操作/请求头/安全方案）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
