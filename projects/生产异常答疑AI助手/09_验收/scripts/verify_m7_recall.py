"""M7 沉淀再召回实测：已归档沉淀的问题，用相似问法提问能否命中。"""
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
    with urllib.request.urlopen(r, timeout=120) as resp:
        return json.loads(resp.read().decode("utf-8", "ignore"))


tok = req("POST", "/api/auth/login", {"username": "employee", "password": "employee123"})["access_token"]
resp = req("POST", "/api/chat/ask", {"question": "CNC加工中心主轴过载报警了怎么办"}, tok)
srcs = resp.get("sources") or []
types = [s.get("source_type") for s in srcs]
print("ANSWER_HEAD:", (resp.get("answer") or "")[:80].replace("\n", " "))
print("SOURCE_TYPES:", types)
print("M7_SEDIMENT_RECALL:", "PASS" if any("沉淀" in (t or "") or "archive" in (t or "") for t in types) else "未命中沉淀来源（来源类型见上）")
