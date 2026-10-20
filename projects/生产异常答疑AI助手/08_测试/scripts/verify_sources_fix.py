"""第 8.5 步人工反馈修复验证：「未找到」类答案不应携带参考来源。"""
import json
import urllib.request

BASE = "http://127.0.0.1:8000"


def req(method, path, data=None, token=None):
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(data).encode() if data is not None else None
    if body:
        headers["Content-Type"] = "application/json"
    r = urllib.request.Request(BASE + path, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=120) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8", "ignore"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8", "ignore"))


_, b = req("POST", "/api/auth/login", {"username": "employee", "password": "employee123"})
tok = b["access_token"]

st, resp = req("POST", "/api/chat/ask", {"question": "如何配置量子纠缠打印机的主板固件"}, tok)
ans = resp.get("answer", "")
srcs = resp.get("sources") or []
print("STATUS:", st)
print("ANSWER_HEAD:", ans[:60].replace("\n", " "))
print("SOURCES_COUNT:", len(srcs))
not_found = "未在知识库中找到相关内容" in ans
print("IS_NOT_FOUND_ANSWER:", not_found)
if not_found and len(srcs) == 0:
    print("VERIFY: PASS（未找到类答案已不携带来源）")
elif not not_found:
    print("VERIFY: SKIP（本次 LLM 未答「未找到」，非目标路径；多试一次）")
else:
    print("VERIFY: FAIL（未找到类答案仍携带来源）")
