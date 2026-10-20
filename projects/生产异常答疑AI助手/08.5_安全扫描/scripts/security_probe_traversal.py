"""SEC-01 复测：清理残留 -> 复测穿越 -> 校验落点 -> 清理测试文档。"""
import json
import os
import time
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8000"
PROJ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 项目根
RUNTIME = os.path.join(PROJ, "runtime")
ESCAPED = os.path.join(RUNTIME, "path_traversal_probe.pdf")
UPLOADS = os.path.join(RUNTIME, "uploads")


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
            return resp.status, resp.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "ignore")


_, b = req("POST", "/api/auth/login", {"username": "admin", "password": "admin123"})
tok = json.loads(b)["access_token"]

# 1. 清理：删除修复前后的探针文档（API 会连带删除落盘文件与向量）
for did in (7, 8):
    st, body = req("DELETE", f"/api/documents/{did}", token=tok)
    print(f"CLEAN doc {did}: {st}")

# 兜底：若残留文件仍在，直接删
if os.path.exists(ESCAPED):
    os.remove(ESCAPED)
    print("CLEAN leftover escaped file: removed")
print("BEFORE_RETEST escaped_exists:", os.path.exists(ESCAPED))

# 2. 复测：同名恶意文件名上传
boundary = "----PROBE" + str(int(time.time()))
fname = "x/../../path_traversal_probe.pdf"
head = (
    f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{fname}"\r\n'
    "Content-Type: application/octet-stream\r\n\r\n"
).encode()
tail = (
    f'\r\n--{boundary}\r\nContent-Disposition: form-data; name="scenario"\r\n\r\nprobe\r\n'
    f"--{boundary}--\r\n"
).encode()
st, body = req("POST", "/api/documents/upload", head + b"%PDF-1.4 probe" + tail, tok,
               ct=f"multipart/form-data; boundary={boundary}")
print("RETEST_UPLOAD:", st, body[:160])
doc_id = json.loads(body).get("document_id") if st == 200 else None

# 3. 校验落点
inside_expected = os.path.join(UPLOADS, f"{doc_id}_path_traversal_probe.pdf") if doc_id else ""
print("ESCAPED_EXISTS:", os.path.exists(ESCAPED), "(期望 False)")
print("INSIDE_UPLOADS_WITH_ID_PREFIX:", os.path.exists(inside_expected), "(期望 True)", os.path.basename(inside_expected))

# 4. 清理复测文档
if doc_id:
    st, _ = req("DELETE", f"/api/documents/{doc_id}", token=tok)
    print(f"CLEAN doc {doc_id}: {st}")
    print("AFTER_CLEAN inside_exists:", os.path.exists(inside_expected))
print("FINAL escaped_exists:", os.path.exists(ESCAPED))
