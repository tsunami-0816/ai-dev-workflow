#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HTTP 客户端：自动 Bearer（构造即注入 header，规则 9）、请求/响应日志、错误体解析。"""
import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field


@dataclass
class Resp:
    status: int
    body: dict
    text: str
    elapsed_ms: int
    headers: dict = field(default_factory=dict)

    def code(self):
        return self.body.get("code") if isinstance(self.body, dict) else None

    def data(self):
        return self.body.get("data") if isinstance(self.body, dict) else None

    def msg(self):
        return self.body.get("msg") if isinstance(self.body, dict) else None


class ApiClient:
    """一个客户端一个身份；token 一进构造函数就写进默认 header，避免假 401。"""

    def __init__(self, base_url, token=None, timeout=20, name="client"):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.name = name
        self.session_headers = {"Accept": "application/json"}
        self.token = None
        if token:
            self.set_token(token)

    def set_token(self, token):
        self.token = token
        self.session_headers["Authorization"] = f"Bearer {token}"

    def clear_token(self):
        self.token = None
        self.session_headers.pop("Authorization", None)

    def request(self, method, path, body=None, headers=None, raw_body=None, timeout=None):
        url = path if path.startswith("http") else self.base_url + path
        hdrs = dict(self.session_headers)
        data = None
        if raw_body is not None:
            data = raw_body
            hdrs["Content-Type"] = "application/json; charset=utf-8"
        elif body is not None:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            hdrs["Content-Type"] = "application/json; charset=utf-8"
        if headers:
            hdrs.update(headers)
        req = urllib.request.Request(url, data=data, headers=hdrs, method=method.upper())
        started = time.time()
        try:
            with urllib.request.urlopen(req, timeout=timeout or self.timeout) as resp:
                text = resp.read().decode("utf-8")
                status = resp.status
                resp_headers = dict(resp.headers)
        except urllib.error.HTTPError as ex:
            text = ex.read().decode("utf-8", errors="replace")
            status = ex.code
            resp_headers = dict(ex.headers)
        except Exception as ex:  # 连接拒绝/超时，明确抛给用例，不伪装成业务失败
            raise RuntimeError(f"{self.name} {method} {url} 连接失败: {ex}") from ex
        elapsed = int((time.time() - started) * 1000)
        try:
            parsed = json.loads(text) if text else {}
        except json.JSONDecodeError:
            parsed = {"_raw": text}
        print(f"[{self.name}] {method.upper()} {path} -> {status} {elapsed}ms {json.dumps(parsed, ensure_ascii=False)[:300]}")
        return Resp(status, parsed, text, elapsed, resp_headers)

    def get(self, path, headers=None, timeout=None):
        return self.request("GET", path, headers=headers, timeout=timeout)

    def post(self, path, body=None, headers=None, raw_body=None, timeout=None):
        return self.request("POST", path, body=body, headers=headers, raw_body=raw_body, timeout=timeout)

    def options(self, path, headers=None):
        return self.request("OPTIONS", path, headers=headers)


def login(base_url, account, password, timeout=20):
    client = ApiClient(base_url, timeout=timeout, name="login")
    resp = client.post("/api/auth/login", {"account": account, "password": password})
    assert resp.status == 200 and resp.code() == 0, f"登录失败 {resp.status} {resp.text[:200]}"
    return resp.data()["token"], resp.data()["userId"]
