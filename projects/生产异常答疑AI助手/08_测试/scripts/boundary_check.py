"""第 8 步全量测试 · 边界/异常场景探测脚本（找 P0/P1 Bug）。
只探测，不改业务逻辑。每条断言打印 实际状态码，人工据此判定是否为 Bug。
"""
import json
import mimetypes
import os
import time
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8000"


def req(method, path, data=None, token=None, ct=None):
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = None
    if data is not None:
        headers["Content-Type"] = ct or "application/json"
        body = data if ct else json.dumps(data).encode()
    r = urllib.request.Request(BASE + path, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            return resp.status, resp.read().decode("utf-8", errors="ignore")
    except urllib.error.HTTPError as e:
        return e.code, (e.read().decode("utf-8", errors="ignore") if e.fp else "")
    except Exception as e:
        return 0, f"{type(e).__name__}: {e}"


def login(u, p):
    st, body = req("POST", "/api/auth/login", {"username": u, "password": p})
    d = json.loads(body) if body else {}
    return d.get("access_token")


def multipart_upload(token, filename, content_bytes, scenario="process"):
    boundary = "----BOUND" + str(int(time.time()))
    head = (
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{filename}\"\r\n"
        f"Content-Type: application/octet-stream\r\n\r\n"
    ).encode()
    tail = (
        f"\r\n--{boundary}\r\nContent-Disposition: form-data; name=\"scenario\"\r\n\r\n{scenario}\r\n"
        f"--{boundary}--\r\n"
    ).encode()
    return req("POST", "/api/documents/upload", head + content_bytes + tail, token,
               ct=f"multipart/form-data; boundary={boundary}")


def main():
    admin = login("admin", "admin123")
    emp = login("employee", "employee123")
    repair = login("repair", "repair123")
    print("tokens:", bool(admin), bool(emp), bool(repair))

    # 1. 上传不支持的文件类型
    print("\n[1] 上传 .txt（不支持类型）-> 期望 400")
    print(" ", req("POST", "/api/documents/upload", None, admin) if False else multipart_upload(admin, "x.txt", b"hello"))

    # 2. employee 删除文档 -> 期望 403
    print("\n[2] employee 删除文档 -> 期望 403")
    print(" ", req("DELETE", "/api/documents/1", token=emp))

    # 3. 删除不存在文档 -> 期望 404
    print("\n[3] admin 删除不存在文档 id=9999 -> 期望 404")
    print(" ", req("DELETE", "/api/documents/9999", token=admin))

    # 4. 重建不存在文档 -> 期望 404
    print("\n[4] admin 重建不存在文档 id=9999 -> 期望 404")
    print(" ", req("POST", "/api/documents/9999/rebuild", token=admin))

    # 5. 审核不存在沉淀 -> 期望 404
    print("\n[5] admin 审核不存在沉淀 id=9999 -> 期望 404")
    print(" ", req("POST", "/api/knowledge/9999/review", {"approve": True, "reject_reason": ""}, admin))

    # 6. 查询不存在会话消息 -> 期望 404
    print("\n[6] employee 查不存在会话 id=9999 消息 -> 期望 404")
    print(" ", req("GET", "/api/conversations/9999/messages", token=emp))

    # 7. 标记不存在通知已读 -> 期望 404
    print("\n[7] employee 标记不存在通知 id=9999 已读 -> 期望 404")
    print(" ", req("POST", "/api/notifications/9999/read", token=emp))

    # 8. 重复关闭同一工单（状态机）
    print("\n[8] 状态机：关闭已关闭工单")
    # 先找一个已关闭工单
    st, body = req("GET", "/api/tickets?status=closed&page_size=5", token=admin)
    try:
        items = json.loads(body).get("list", [])
    except Exception:
        items = []
    if items:
        tid = items[0]["id"]
        print(f"  选已关闭工单 {tid} 再次 close -> 期望 400/409 或幂等 200")
        print(" ", req("POST", f"/api/tickets/{tid}/close", {"solution": "dup", "archive": False}, admin))
        print(f"  对 {tid} 再 handle -> 期望 400/409")
        print(" ", req("POST", f"/api/tickets/{tid}/handle", {"content": "after closed"}, admin))
        print(f"  对 {tid} 再 assign -> 期望 400/409")
        print(" ", req("POST", f"/api/tickets/{tid}/assign", token=admin))
    else:
        print("  无已关闭工单，跳过")

    # 9. 越权：employee 访问非本人工单详情
    print("\n[9] 越权：employee 访问非本人工单")
    st, body = req("GET", "/api/tickets?page_size=3", token=admin)
    try:
        items = json.loads(body).get("list", [])
    except Exception:
        items = []
    if items:
        tid = items[0]["id"]
        print(f"  employee GET /api/tickets/{tid} -> 期望 403")
        print(" ", req("GET", f"/api/tickets/{tid}", token=emp))

    # 10. 关闭工单时 archive=true 但 solution 为空 -> 沉淀生成行为
    print("\n[10] 关闭工单 archive=true 但 solution 为空（验证沉淀兜底）")
    # 用一个已关闭工单重开不了；新建一个：先 ask 派单
    print("  （跳过：需新建工单，联调已覆盖正常路径）")

    # 11. 重复领取同一工单
    print("\n[11] 重复领取同一工单")
    st, body = req("GET", "/api/tickets?status=pending&page_size=3", token=admin)
    try:
        items = json.loads(body).get("list", [])
    except Exception:
        items = []
    if items:
        tid = items[0]["id"]
        print(f"  对 pending 工单 {tid} 连续 assign 两次 -> 第二次期望幂等或 400")
        print(" ", req("POST", f"/api/tickets/{tid}/assign", token=admin))
        print(" ", req("POST", f"/api/tickets/{tid}/assign", token=admin))
    else:
        print("  无 pending 工单，跳过")


if __name__ == "__main__":
    main()
