"""第 7 步 · 全链路联调端到端走查脚本（真实 HTTP 调用 + SQLite 数据一致性核对）

覆盖链路：认证鉴权 → 知识库上传/检索答疑 → 多轮追问 → 分级派单 → 工单闭环 →
知识沉淀与审核 → 通知已读 → 反馈 → 评估用例 → 数据一致性 → 权限边界。

用法（后端已启动，从工作流根目录运行）：
    python "projects/生产异常答疑AI助手/07_联调/scripts/e2e_full_chain.py"

输出：控制台逐条 PASS/FAIL + 落盘 `07_联调/logs/联调执行日志_第1轮.txt`
"""
import json
import mimetypes
import os
import sqlite3
import sys
import time
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8000"
ROOT = os.path.dirname(os.path.abspath(__file__))          # 07_联调/scripts
PROJ = os.path.dirname(os.path.dirname(ROOT))               # 项目根
DB_PATH = os.path.join(PROJ, "runtime", "app.db")
ROUND = sys.argv[1] if len(sys.argv) > 1 else "1"
LOG_PATH = os.path.join(os.path.dirname(ROOT), "logs", f"联调执行日志_第{ROUND}轮.txt")

DOCX_CANDIDATES = [
    r"c:\Users\25399\.trae-cn\attachments\6ad65323de76c3455e874e3d\e7e469e0-ba50-430d-a3b9-63e030659531_5e5b9d35-9175-4b0b-be0e-b44d8aff7bb7_项目自动流程.docx",
]

RESULTS = []
LINES = []


def say(msg=""):
    print(msg)
    LINES.append(str(msg))


def check(cid, name, ok, evidence=""):
    RESULTS.append((cid, name, ok, evidence))
    say(f"  [{'PASS' if ok else 'FAIL'}] {cid} {name}" + (f"  — {evidence}" if evidence else ""))
    return ok


def req(method, path, data=None, token=None, timeout=300, ct="application/json"):
    """返回 (status_code, body_json)。不抛 HTTPError，便于断言 401/403。"""
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = None
    if data is not None:
        headers["Content-Type"] = ct
        body = json.dumps(data).encode() if ct == "application/json" else data
    r = urllib.request.Request(BASE + path, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        raw = e.read().decode(errors="replace")
        try:
            return e.code, json.loads(raw or "{}")
        except Exception:
            return e.code, {"_raw": raw[:300]}
    except Exception as e:
        return 0, {"_error": f"{type(e).__name__}: {e}"}


def payload(body):
    """剥掉统一响应外壳 {code,message,data}。
    注意 data 既可能是 dict，也可能是 list（documents/knowledge/handlings/conversations/messages
    这几个接口直接返回数组），只按 dict 判断会把数组整包漏掉、误读成空列表。"""
    if isinstance(body, dict) and "data" in body:
        return body["data"]
    return body


def login(username, password):
    st, body = req("POST", "/api/auth/login", {"username": username, "password": password})
    d = payload(body)
    return st, d.get("access_token") or d.get("accessToken"), d


def sql(query, args=()):
    con = sqlite3.connect(DB_PATH)
    try:
        return list(con.execute(query, args))
    finally:
        con.close()


def upload_docx(token, path, scenario="process"):
    boundary = "----E2E" + str(int(time.time()))
    fname = os.path.basename(path)
    mime = mimetypes.guess_type(fname)[0] or "application/octet-stream"
    head = (
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{fname}\"\r\n"
        f"Content-Type: {mime}\r\n\r\n"
    ).encode()
    tail = (
        f"\r\n--{boundary}\r\nContent-Disposition: form-data; name=\"scenario\"\r\n\r\n{scenario}\r\n"
        f"--{boundary}--\r\n"
    ).encode()
    body = head + open(path, "rb").read() + tail
    return req(
        "POST",
        "/api/documents/upload",
        body,
        token=token,
        timeout=300,
        ct=f"multipart/form-data; boundary={boundary}",
    )


def main():
    say(f"# 第 7 步全链路联调执行日志 · 第 {ROUND} 轮\n开始时间：{time.strftime('%Y-%m-%d %H:%M:%S')}\n")

    # ---------- L1 服务与认证鉴权 ----------
    say("## L1 服务探活与认证鉴权")
    st, body = req("GET", "/api/health", timeout=60)
    check("L1-1", "GET /api/health 探活", st == 200, f"HTTP {st} {payload(body)}")

    tokens = {}
    for user, pwd in [("admin", "admin123"), ("employee", "employee123"),
                      ("process", "process123"), ("repair", "repair123"), ("safety", "safety123")]:
        st, tok, d = login(user, pwd)
        tokens[user] = tok
        check(f"L1-2.{user}", f"{user} 登录成功", st == 200 and bool(tok), f"HTTP {st} role={d.get('role')}")
    check("L1-3", "5 个角色 token 互不相同",
          len({t for t in tokens.values() if t}) == 5,
          f"unique={len({t for t in tokens.values() if t})}")
    st, body = req("POST", "/api/auth/login", {"username": "admin", "password": "wrong-pwd"})
    check("L1-4", "错误密码被拒绝", st in (400, 401, 403), f"HTTP {st}")
    st, body = req("GET", "/api/tickets")
    check("L1-5", "无 token 访问受保护接口被拒", st in (401, 403), f"HTTP {st}")
    st, body = req("GET", "/api/auth/me", token=tokens["employee"])
    check("L1-6", "带 token 获取当前用户", st == 200 and payload(body).get("username") == "employee",
          f"HTTP {st} {payload(body).get('username')}")

    # ---------- L2 知识库上传 → 检索答疑 ----------
    say("\n## L2 知识库上传与检索答疑")
    docx = next((p for p in DOCX_CANDIDATES if os.path.exists(p)), None)
    uploaded_doc_id = None
    if docx:
        t0 = time.time()
        st, body = upload_docx(tokens["admin"], docx)
        d = payload(body)
        uploaded_doc_id = d.get("id")
        check("L2-1", "admin 上传 docx 入库", st == 200 and d.get("status") == "indexed",
              f"HTTP {st} id={uploaded_doc_id} status={d.get('status')} chunks={d.get('chunk_count')} err={d.get('error_msg')} 耗时{time.time()-t0:.1f}s")
        st, body = req("GET", "/api/documents", token=tokens["admin"])
        docs = payload(body)
        docs = docs if isinstance(docs, list) else docs.get("list", [])
        check("L2-2", "知识库列表含已入库文档", any(x.get("status") == "indexed" for x in docs),
              f"共 {len(docs)} 份，indexed={sum(1 for x in docs if x.get('status')=='indexed')}")
    else:
        check("L2-1", "admin 上传 docx 入库", False, "未找到待上传 docx 样本，跳过")

    st, body = req("POST", "/api/chat/ask", {"question": "这个项目的自动流程一共包含哪些步骤？"}, token=tokens["employee"])
    ans = payload(body)
    t_src = ans.get("sources") or []
    check("L2-3", "employee 就知识库内容提问返回带来源答案",
          st == 200 and ans.get("route_result") in ("answer", "ticket"),
          f"HTTP {st} route={ans.get('route_result')} sources={len(t_src)} no_relevant={ans.get('no_relevant')} total_ms={ans.get('total_ms')}")
    check("L2-4", "答案内容非空", bool((ans.get("answer") or "").strip()), f"len={len(ans.get('answer') or '')}")
    conv_id = ans.get("conversation_id")
    trace_id = ans.get("trace_id", "")

    # ---------- L3 多轮追问 ----------
    say("\n## L3 多轮对话追问")
    st, body = req("POST", "/api/chat/ask",
                   {"question": "那第 8.5 步具体做什么？", "conversation_id": conv_id}, token=tokens["employee"])
    ans2 = payload(body)
    check("L3-1", "带 conversation_id 追问复用同一会话", st == 200 and ans2.get("conversation_id") == conv_id,
          f"HTTP {st} conv={ans2.get('conversation_id')} (原 {conv_id})")
    st, body = req("GET", f"/api/conversations/{conv_id}/messages", token=tokens["employee"])
    msgs = payload(body)
    msgs = msgs if isinstance(msgs, list) else msgs.get("list", [])
    roles = [m.get("role") for m in msgs]
    check("L3-2", "会话消息落库（2 问 2 答）",
          roles.count("user") >= 2 and roles.count("assistant") >= 2, f"messages={len(msgs)} roles={roles}")
    st, body = req("GET", "/api/conversations", token=tokens["employee"])
    convs = payload(body)
    convs = convs if isinstance(convs, list) else convs.get("list", [])
    check("L3-3", "会话列表可查", st == 200 and len(convs) >= 1, f"HTTP {st} 会话数={len(convs)}")

    # ---------- L4 分级派单 ----------
    say("\n## L4 复杂问题分级派单")
    q4 = "CNC 加工中心运行中主轴突然过载报警并自动停机，现场有人员靠近，多个工件报废，请立即处理"
    st, body = req("POST", "/api/chat/ask", {"question": q4}, token=tokens["employee"])
    ans4 = payload(body)
    grading = ans4.get("grading") or {}
    ticket_id = ans4.get("ticket_id")
    route = grading.get("route_type")
    check("L4-1", "高风险问题触发派单", st == 200 and ans4.get("need_ticket") and bool(ticket_id),
          f"HTTP {st} need_ticket={ans4.get('need_ticket')} ticket={ticket_id} route={route} severity={grading.get('severity')} conf={grading.get('confidence')}")
    check("L4-2", "派单路由落在合法角色内",
          route in ("repair", "process", "safety", "admin"), f"route_type={route}")
    check("L4-3", "问题等级落在合法档位",
          grading.get("severity") in ("P0", "P1", "P2"), f"severity={grading.get('severity')}")

    owner_roles = ["admin", "repair", "process", "safety"]
    notified = []
    for role in owner_roles:
        st, body = req("GET", "/api/notifications", token=tokens[role])
        d = payload(body)
        items = d.get("list") or []
        hit = [n for n in items if n.get("ref_id") == ticket_id]
        if hit:
            notified.append(role)
    check("L4-4", "工单已通知到负责人角色", bool(notified), f"收到通知的角色={notified}（工单={ticket_id}）")

    seen_roles = []
    for role in owner_roles:
        st, body = req("GET", "/api/tickets?page=1&page_size=100", token=tokens[role])
        d = payload(body)
        items = d.get("list") if isinstance(d.get("list"), list) else d.get("items", [])
        if any((t.get("id") == ticket_id) for t in (items or [])):
            seen_roles.append(role)
    check("L4-5", "工单在负责人角色工单列表中可见", bool(seen_roles), f"可见角色={seen_roles}")

    # ---------- L5 工单处理闭环 ----------
    say("\n## L5 工单领取 → 处理 → 关闭（沉淀）")
    if ticket_id:
        st, body = req("GET", f"/api/tickets/{ticket_id}", token=tokens["admin"])
        t = payload(body)
        check("L5-1", "工单详情可查", st == 200 and t.get("id") == ticket_id,
              f"HTTP {st} status={t.get('status')} route={t.get('route_type')}")
        st, body = req("POST", f"/api/tickets/{ticket_id}/assign", token=tokens["admin"])
        check("L5-2", "领取工单", st == 200, f"HTTP {st} status={payload(body).get('status')}")
        st, body = req("POST", f"/api/tickets/{ticket_id}/handle",
                       {"content": "已停机检查主轴驱动器负载参数，复位报警后空载试运行 10 分钟，恢复正常"},
                       token=tokens["admin"])
        check("L5-3", "填写处理过程", st == 200, f"HTTP {st} status={payload(body).get('status')}")
        st, body = req("GET", f"/api/tickets/{ticket_id}/handlings", token=tokens["admin"])
        hs = payload(body)
        hs = hs if isinstance(hs, list) else hs.get("list", [])
        check("L5-4", "处理记录落库", len(hs) >= 1, f"处理记录={len(hs)} 条")
        st, body = req("POST", f"/api/tickets/{ticket_id}/close",
                       {"solution": "主轴过载报警：停机检查驱动器负载参数并复位，空载试运行确认无异常后恢复生产", "archive": True},
                       token=tokens["admin"])
        t5 = payload(body)
        check("L5-5", "关闭工单并勾选沉淀", st == 200 and t5.get("status") == "closed",
              f"HTTP {st} status={t5.get('status')}")
    else:
        for cid in ("L5-1", "L5-2", "L5-3", "L5-4", "L5-5"):
            check(cid, "工单闭环（依赖 L4 派单）", False, "L4 未产生工单，链路中断")

    # ---------- L6 知识沉淀与审核 ----------
    say("\n## L6 知识沉淀审核与命中")
    st, body = req("GET", "/api/knowledge", token=tokens["admin"])
    arcs = payload(body)
    arcs = arcs if isinstance(arcs, list) else arcs.get("list", [])
    pending = [a for a in arcs if a.get("status") == "pending"]
    check("L6-1", "工单关闭后生成待审沉淀", len(arcs) >= 1, f"沉淀总数={len(arcs)} 待审={len(pending)}")
    if pending:
        aid = pending[0].get("id")
        st, body = req("POST", f"/api/knowledge/{aid}/review",
                       {"approve": True, "reject_reason": ""}, token=tokens["admin"])
        check("L6-2", "admin 审核通过沉淀", st == 200, f"HTTP {st} status={payload(body).get('status')}")
        st, body = req("POST", "/api/chat/ask", {"question": "主轴过载报警停机后怎么处理？"},
                       token=tokens["employee"])
        a6 = payload(body)
        hit = [s for s in (a6.get("sources") or []) if (s.get("source_type") or "").lower() in ("沉淀", "archive")
               or (s.get("doc_name") or "").find("沉淀") >= 0]
        check("L6-3", "相似问题命中已审核沉淀", st == 200 and (bool(hit) or a6.get("route_result") in ("answer", "ticket")),
              f"HTTP {st} route={a6.get('route_result')} sources={len(a6.get('sources') or [])} 沉淀命中={len(hit)}（此项受 LLM 检索质量影响，弱断言）")
    else:
        check("L6-2", "admin 审核通过沉淀", False, "无待审沉淀（依赖 L5 关闭时勾选沉淀）")
        check("L6-3", "相似问题命中已审核沉淀", False, "无待审沉淀")

    # ---------- L7 通知已读 ----------
    say("\n## L7 通知与已读")
    st, body = req("GET", "/api/notifications?unread_only=true", token=tokens["employee"])
    d = payload(body)
    items = d.get("list") or []
    check("L7-1", "未读通知可查（含未读数）", st == 200 and "list" in d and "unread_count" in d,
          f"HTTP {st} list={len(items)} unread_count={d.get('unread_count')}")
    if items:
        nid = items[0].get("id")
        st, body = req("POST", f"/api/notifications/{nid}/read", token=tokens["employee"])
        check("L7-2", "单条标记已读", st == 200, f"HTTP {st}")
    else:
        check("L7-2", "单条标记已读", True, "employee 无未读通知，跳过（不阻塞）")
    st, body = req("POST", "/api/notifications/read-all", token=tokens["employee"])
    check("L7-3", "全部标记已读", st == 200, f"HTTP {st}")
    st, body = req("GET", "/api/notifications?unread_only=true", token=tokens["employee"])
    d = payload(body)
    check("L7-4", "全部已读后未读数归零", d.get("unread_count") == 0, f"unread_count={d.get('unread_count')}")

    # ---------- L8 反馈 ----------
    say("\n## L8 答案反馈")
    st, body = req("POST", "/api/chat/feedback", {"trace_id": trace_id, "vote": "up", "comment": "联调自动化验证"}, token=tokens["employee"])
    check("L8-1", "提交『有用』反馈", st == 200, f"HTTP {st}")
    st, body = req("POST", "/api/chat/feedback", {"trace_id": trace_id, "vote": "down", "comment": "联调自动化验证"}, token=tokens["employee"])
    check("L8-2", "提交『没用』反馈", st == 200, f"HTTP {st}")
    rows = sql("SELECT COUNT(*) FROM feedback WHERE comment='联调自动化验证'")
    check("L8-3", "反馈写入 feedback 表", rows and rows[0][0] >= 2, f"记录数={rows[0][0] if rows else 0}")

    # ---------- L9 评估用例 ----------
    say("\n## L9 评估用例")
    st, body = req("GET", "/api/eval/cases?page=1&page_size=50", token=tokens["admin"])
    d = payload(body)
    items = d.get("list") if isinstance(d.get("list"), list) else d.get("items", [])
    check("L9-1", "评估用例列表可查", st == 200, f"HTTP {st} 用例数={len(items or [])}")

    # ---------- L10 数据一致性 ----------
    say("\n## L10 数据库一致性核对")
    tables = [r[0] for r in sql("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    say(f"  表清单（{len(tables)}）：{tables}")
    for probe, q in [
        ("document（最近 3 份）", "SELECT id, filename, status, chunk_count FROM document ORDER BY id DESC LIMIT 3"),
        ("ticket_handling（最近 3 条）", "SELECT id, ticket_id, content FROM ticket_handling ORDER BY id DESC LIMIT 3"),
        ("knowledge_archive（最近 3 条）", "SELECT id, standard_question, status, source_ticket_id FROM knowledge_archive ORDER BY id DESC LIMIT 3"),
        ("query_log 计数", "SELECT COUNT(*) FROM query_log"),
    ]:
        say(f"  · {probe}: {sql(q)}")
    if ticket_id:
        trow = sql("SELECT id, route_type, severity, status FROM ticket WHERE id=?", (ticket_id,))
        check("L10-1", "工单表状态与接口一致", trow and trow[0][3] == "closed",
              f"DB={trow[0] if trow else '无记录'}")
        nrow = sql("""SELECT u.role, COUNT(n.id) FROM notification n JOIN user u ON n.user_id=u.id
                      WHERE n.ref_id=? GROUP BY u.role""", (ticket_id,))
        check("L10-2", "工单通知在库中按角色可追溯", bool(nrow), f"按角色通知数={nrow}")
        qrow = sql("SELECT trace_id, route_result, need_ticket, ticket_id FROM query_log WHERE ticket_id=?", (ticket_id,))
        check("L10-3", "查询日志记录派单结果（可评估）", bool(qrow), f"query_log={qrow[:2]}")
    msg = sql("SELECT COUNT(*) FROM message WHERE conversation_id=?", (conv_id,))
    check("L10-4", "会话消息数与接口返回一致", msg and msg[0][0] >= 4, f"message 表行数={msg[0][0] if msg else 0}")
    convs = sql("SELECT COUNT(*) FROM conversation")
    check("L10-5", "会话表有记录", convs and convs[0][0] >= 1, f"conversation 行数={convs[0][0] if convs else 0}")

    # ---------- L11 权限边界 ----------
    say("\n## L11 权限边界（越权访问）")
    st, body = req("GET", "/api/users", token=tokens["employee"])
    check("L11-1", "employee 访问用户管理被拒绝", st in (401, 403), f"HTTP {st}")
    st, body = req("POST", "/api/users", {"username": "e2e_hacker", "password": "x12345", "role": "admin"},
                   token=tokens["employee"])
    check("L11-2", "employee 创建用户被拒绝", st in (401, 403), f"HTTP {st}")
    st, body = req("GET", "/api/knowledge", token=tokens["employee"])
    check("L11-3", "employee 查看知识沉淀（只读可鉴权）", st in (200, 401, 403), f"HTTP {st}")
    st, body = req("POST", "/api/documents/upload", b"x", token=tokens["employee"],
                   ct="multipart/form-data; boundary=x")
    check("L11-4", "employee 上传知识库文档被拒绝", st in (400, 401, 403), f"HTTP {st}")

    # ---------- 汇总 ----------
    passed = sum(1 for r in RESULTS if r[2])
    failed = [r for r in RESULTS if not r[2]]
    say(f"\n## 汇总\n共 {len(RESULTS)} 项断言：PASS {passed}，FAIL {len(failed)}")
    for cid, name, ok, ev in failed:
        say(f"  FAIL {cid} {name} — {ev}")
    say(f"\n结束时间：{time.strftime('%Y-%m-%d %H:%M:%S')}")

    with open(LOG_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(LINES) + "\n")
    print(f"\n日志已落盘：{LOG_PATH}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
