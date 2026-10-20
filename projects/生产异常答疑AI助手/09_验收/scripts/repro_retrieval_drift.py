"""第 9 步验收问题复现：领域内问题是否被无关文档带偏 + 检索得分诊断。"""
import json
import urllib.request

BASE = "http://127.0.0.1:8000"


def req(method, path, data=None, token=None, timeout=120):
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(data).encode() if data is not None else None
    if body:
        headers["Content-Type"] = "application/json"
    r = urllib.request.Request(BASE + path, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8", "ignore"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8", "ignore"))


_, b = req("POST", "/api/auth/login", {"username": "employee", "password": "employee123"})
tok = b["access_token"]

# 1. 知识库现有文档（确认是否存在传送带相关内容）
_, ab = req("POST", "/api/auth/login", {"username": "admin", "password": "admin123"})
st, docs = req("GET", "/api/documents", token=ab["access_token"])
print("== 知识库文档 ==")
items = docs if isinstance(docs, list) else (docs.get("documents") or docs.get("data") or [])
for d in items:
    print(f"  id={d.get('id')} status={d.get('status')} name={d.get('filename') or d.get('name')}")

# 2. 复现用户问题（库外，应拒答）
st, resp = req("POST", "/api/chat/ask", {"question": "传送带跑偏怎么调？"}, tok)
print("\n== 提问「传送带跑偏怎么调？」==")
print("route:", resp.get("route_result"), "| confidence:", resp.get("confidence"), "| no_relevant:", resp.get("no_relevant"))
print("answer_head:", (resp.get("answer") or "")[:120].replace("\n", " "))
print("sources:", [(s.get("doc_name", "")[-20:], s.get("page")) for s in (resp.get("sources") or [])])

# 3. 库内问题对照（应正常回答且带来源）
st2, resp2 = req("POST", "/api/chat/ask", {"question": "人工检查点是什么？"}, tok)
print("\n== 对照「人工检查点是什么？」==")
print("route:", resp2.get("route_result"), "| no_relevant:", resp2.get("no_relevant"))
print("answer_head:", (resp2.get("answer") or "")[:100].replace("\n", " "))
print("sources_count:", len(resp2.get("sources") or []))
