"""后端 API 客户端：封装 requests，统一 token 与错误处理。
token 与 user 存于 streamlit session_state，由 app.py 初始化。
"""
from typing import Any, Optional

import requests
import streamlit as st

BASE_URL = "http://127.0.0.1:8000/api"
TIMEOUT = 120


class ApiError(Exception):
    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(f"[{code}] {message}")


def _headers() -> dict:
    token = st.session_state.get("token", "")
    h = {"Content-Type": "application/json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def _request(method: str, path: str, **kwargs) -> Any:
    url = f"{BASE_URL}{path}"
    kwargs.setdefault("timeout", TIMEOUT)
    if "json" in kwargs:
        kwargs["headers"] = {**_headers(), **kwargs.get("headers", {})}
    else:
        kwargs["headers"] = _headers()
    try:
        resp = requests.request(method, url, **kwargs)
    except requests.ConnectionError:
        raise ApiError(5003, "无法连接后端服务，请确认后端已启动 (http://127.0.0.1:8000)")
    except requests.Timeout:
        raise ApiError(5003, "请求超时，请稍后重试")
    if resp.status_code in (401, 403):
        st.session_state["token"] = ""
        st.session_state["user"] = None
        raise ApiError(resp.status_code, "登录已失效，请重新登录")
    try:
        data = resp.json()
    except Exception:
        raise ApiError(resp.status_code, f"响应解析失败: {resp.text[:200]}")
    if resp.status_code >= 400 or (isinstance(data, dict) and data.get("code", 0) not in (0, None)):
        code = data.get("code", resp.status_code) if isinstance(data, dict) else resp.status_code
        msg = data.get("message", "请求失败") if isinstance(data, dict) else "请求失败"
        raise ApiError(code, msg)
    return data.get("data", data) if isinstance(data, dict) else data


# ===== 认证 =====
def login(username: str, password: str) -> dict:
    data = _request("POST", "/auth/login", json={"username": username, "password": password})
    return data


def me() -> dict:
    return _request("GET", "/auth/me")


# ===== 用户管理 =====
def list_users() -> list:
    return _request("GET", "/users")


def create_user(username: str, password: str, role: str, display_name: str = "") -> dict:
    return _request(
        "POST",
        "/users",
        json={"username": username, "password": password, "role": role, "display_name": display_name},
    )


# ===== 知识库文档 =====
def upload_document(file_bytes: bytes, filename: str, scenario: str = "") -> dict:
    files = {"file": (filename, file_bytes)}
    data = {"scenario": scenario}
    # multipart 不设 Content-Type，让 requests 自动生成
    headers = {"Authorization": f"Bearer {st.session_state.get('token','')}"}
    resp = requests.post(f"{BASE_URL}/documents/upload", files=files, data=data, headers=headers, timeout=TIMEOUT)
    if resp.status_code >= 400:
        d = resp.json()
        raise ApiError(d.get("code", resp.status_code), d.get("message", "上传失败"))
    return resp.json().get("data", resp.json())


def list_documents() -> list:
    return _request("GET", "/documents")


def delete_document(doc_id: int) -> dict:
    return _request("DELETE", f"/documents/{doc_id}")


def rebuild_document(doc_id: int) -> dict:
    return _request("POST", f"/documents/{doc_id}/rebuild")


# ===== 问答 =====
def ask(question: str, conversation_id: Optional[int] = None, scenario: Optional[str] = None) -> dict:
    body = {"question": question}
    if conversation_id:
        body["conversation_id"] = conversation_id
    if scenario:
        body["scenario"] = scenario
    return _request("POST", "/chat/ask", json=body)


def feedback(trace_id: str, vote: str, comment: str = "") -> dict:
    return _request("POST", "/chat/feedback", json={"trace_id": trace_id, "vote": vote, "comment": comment})


# ===== 会话 =====
def list_conversations() -> list:
    return _request("GET", "/conversations")


def list_messages(conversation_id: int) -> list:
    return _request("GET", f"/conversations/{conversation_id}/messages")


# ===== 工单 =====
def list_tickets(status: Optional[str] = None, route_type: Optional[str] = None, page: int = 1, page_size: int = 20) -> dict:
    params = {"page": page, "page_size": page_size}
    if status:
        params["status"] = status
    if route_type:
        params["route_type"] = route_type
    return _request("GET", "/tickets", params=params)


def get_ticket(ticket_id: str) -> dict:
    return _request("GET", f"/tickets/{ticket_id}")


def assign_ticket(ticket_id: str) -> dict:
    return _request("POST", f"/tickets/{ticket_id}/assign")


def handle_ticket(ticket_id: str, content: str) -> dict:
    return _request("POST", f"/tickets/{ticket_id}/handle", json={"content": content})


def close_ticket(ticket_id: str, solution: str = "", archive: bool = False) -> dict:
    return _request("POST", f"/tickets/{ticket_id}/close", json={"solution": solution, "archive": archive})


def list_handlings(ticket_id: str) -> list:
    return _request("GET", f"/tickets/{ticket_id}/handlings")


# ===== 通知 =====
def list_notifications(unread_only: bool = False) -> dict:
    return _request("GET", "/notifications", params={"unread_only": unread_only})


def mark_read(notif_id: int) -> dict:
    return _request("POST", f"/notifications/{notif_id}/read")


def mark_all_read() -> dict:
    return _request("POST", "/notifications/read-all")


# ===== 知识沉淀 =====
def list_archives(status: Optional[str] = None) -> list:
    params = {"status": status} if status else None
    return _request("GET", "/knowledge", params=params)


def review_archive(archive_id: int, approve: bool, reject_reason: str = "") -> dict:
    return _request(
        "POST",
        f"/knowledge/{archive_id}/review",
        json={"approve": approve, "reject_reason": reject_reason},
    )


# ===== 评估 =====
def list_cases(page: int = 1, page_size: int = 50) -> dict:
    return _request("GET", "/eval/cases", params={"page": page, "page_size": page_size})


# ===== 健康检查 =====
def health() -> dict:
    resp = requests.get(f"{BASE_URL}/health", timeout=5)
    return resp.json()
