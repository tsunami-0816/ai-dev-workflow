"""强制触发知识库兜底工单，验证4角色通知"""
import json, sqlite3, time, urllib.request

def req(m, u, d=None, t=None, to=180):
    h = {}
    if t: h["Authorization"] = f"Bearer {t}"
    if d is not None: h["Content-Type"] = "application/json"
    b = json.dumps(d).encode() if d is not None else None
    r = urllib.request.Request(u, data=b, headers=h, method=m)
    try:
        return json.load(urllib.request.urlopen(r, timeout=to))
    except Exception as e:
        print(f"  API FAIL: {e}")
        raise

BASE = "http://127.0.0.1:8000"

# login
l = req("POST", f"{BASE}/api/auth/login", {"username":"employee","password":"employee123"})
t = (l.get("data") or {}).get("access_token") or l.get("access_token")
print("employee login OK")

# ask something that WILL have no relevant content
q = "xyzzyplugh 反重力等离子场 第42号 永动机调试"
t0 = time.time()
ans = req("POST", f"{BASE}/api/chat/ask", {"question": q}, t, to=180)
print(f"ASK ({time.time()-t0:.1f}s): route={ans.get('route_result')}, ticket={ans.get('ticket_id')}, sources={len(ans.get('sources') or [])}")
g = ans.get("grading", {})
print(f"  grading: need_ticket={g.get('need_ticket')}, route_type={g.get('route_type')}, conf={g.get('confidence')}")

tid = ans.get("ticket_id")
if tid:
    db = sqlite3.connect("data/app.db")
    print(f"\n=== ticket {tid} ===")
    for row in db.execute(f"SELECT id, route_type, severity FROM ticket WHERE id='{tid}'"):
        print(" ", row)
    print(f"\n=== notifications for {tid} per role ===")
    for row in db.execute(f"""
        SELECT u.role, COUNT(n.id) as cnt
        FROM notification n JOIN user u ON n.user_id = u.id
        WHERE n.ref_id='{tid}'
        GROUP BY u.role
        ORDER BY u.role
    """):
        print(f"  role={row[0]}, count={row[1]}")
    # 还查一下有没有"知识库无答案"关键字
    print(f"\n=== KB-fallback notifications (title含'知识库无答案') ===")
    for row in db.execute(f"""
        SELECT u.username, u.role, n.title, n.ref_id
        FROM notification n JOIN user u ON n.user_id = u.id
        WHERE n.ref_id='{tid}' AND n.title LIKE '%知识库无答案%'
        ORDER BY u.role
    """):
        print(" ", row)
    db.close()
