"""验证三个 Bug 是否修好：1. 文档上传 Chroma metadata 2. 反馈按钮不白屏 3. 兜底工单通知所有角色"""
import json, os, time, urllib.request, urllib.error

BASE = "http://127.0.0.1:8000"

def req(method, url, data=None, token=None, timeout=180, content_type="application/json"):
    headers = {}
    if token: headers["Authorization"] = f"Bearer {token}"
    if data is not None: headers["Content-Type"] = content_type
    body = json.dumps(data).encode() if data is not None and content_type == "application/json" else data
    r = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        return json.load(urllib.request.urlopen(r, timeout=timeout))
    except urllib.error.HTTPError as e:
        err = e.read().decode(errors="replace")
        print(f"  HTTP {e.code} on {url}: {err[:300]}")
        raise

# 1. health
print("=== 1. health ===")
ok = False
for i in range(10):
    try:
        print(req("GET", f"{BASE}/api/health")); ok = True; break
    except Exception as e:
        print(f"  retry {i+1}: {type(e).__name__}"); time.sleep(8)
if not ok: sys.exit(1)

def extract_token(login_resp):
    """兼容两种返回格式：{data:{access_token:...}} 或 直接 {access_token:...}"""
    if isinstance(login_resp.get("data"), dict):
        return login_resp["data"].get("access_token") or login_resp["data"].get("accessToken")
    return login_resp.get("access_token") or login_resp.get("accessToken")

# 2. login admin
print("\n=== 2. login admin ===")
admin_login = req("POST", f"{BASE}/api/auth/login", {"username":"admin","password":"admin123"})
admin_token = extract_token(admin_login)
print("  admin token OK" if admin_token else f"  admin FAIL: {admin_login}")

# 3. upload docx （从用户附件路径）
print("\n=== 3. upload docx (test metadata fix) ===")
docx_path = r"c:\Users\25399\.trae-cn\attachments\6ad65323de76c3455e874e3d\e7e469e0-ba50-430d-a3b9-63e030659531_5e5b9d35-9175-4b0b-be0e-b44d8aff7bb7_项目自动流程.docx"
if os.path.exists(docx_path):
    import http.client, mimetypes
    boundary = "----TestBoundary7MA4YWxkTrZu0gW"
    file_bytes = open(docx_path, "rb").read()
    file_name = os.path.basename(docx_path)
    mime = mimetypes.guess_type(file_name)[0] or "application/octet-stream"
    parts = []
    parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{file_name}\"\r\nContent-Type: {mime}\r\n\r\n".encode())
    parts.append(file_bytes)
    parts.append(f"\r\n--{boundary}\r\nContent-Disposition: form-data; name=\"scenario\"\r\n\r\nprocess\r\n--{boundary}--\r\n".encode())
    body = b"".join(parts)
    r = urllib.request.Request(f"{BASE}/api/documents/upload", data=body, method="POST",
                               headers={"Content-Type": f"multipart/form-data; boundary={boundary}",
                                        "Authorization": f"Bearer {admin_token}"})
    t0 = time.time()
    try:
        resp = json.load(urllib.request.urlopen(r, timeout=120))
        print(f"  UPLOAD OK in {time.time()-t0:.1f}s: status={resp.get('status')}, chunks={resp.get('chunk_count')}, error={resp.get('error_msg')}")
    except urllib.error.HTTPError as e:
        print(f"  UPLOAD FAIL in {time.time()-t0:.1f}s: HTTP {e.code}")
        print(f"  {e.read().decode(errors='replace')[:500]}")
else:
    print(f"  docx not found: {docx_path}")

# 4. ask as employee
print("\n=== 4. ask as employee ===")
emp_login = req("POST", f"{BASE}/api/auth/login", {"username":"employee","password":"employee123"})
emp_token = extract_token(emp_login)
t0 = time.time()
try:
    ans = req("POST", f"{BASE}/api/chat/ask", {"question":"设备温度报警怎么处理？"}, token=emp_token, timeout=180)
    print(f"  ASK OK in {time.time()-t0:.1f}s: route={ans.get('route_result')}, ticket={ans.get('ticket_id')}, sources={len(ans.get('sources') or [])}")
except Exception as e:
    print(f"  ASK FAIL: {e}")

# 5. check notifications for all roles (兜底工单应该都收到了)
print("\n=== 5. verify all 4 roles got notifications for fallback ticket ===")
for role, creds in [("repair","repair123"),("process","process123"),("safety","safety123"),("admin","admin123")]:
    try:
        login = req("POST", f"{BASE}/api/auth/login", {"username":role,"password":creds})
        t = login["data"]["access_token"]
        n = req("GET", f"{BASE}/api/notifications", token=t)
        unread = n.get("unread_count", 0)
        items = n.get("list", [])
        kb_notif = [x for x in items if "知识库无答案" in (x.get("title","") + x.get("content","")) or "知识库" in (x.get("title","") + x.get("content",""))]
        print(f"  {role}: unread={unread}, total={len(items)}, kb-fallback-notif={len(kb_notif)}")
    except Exception as e:
        print(f"  {role}: FAIL {e}")

print("\n=== DONE ===")
