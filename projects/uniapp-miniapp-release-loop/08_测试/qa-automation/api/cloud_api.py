#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""云函数 apiProxy 封装（action/payload/token 协议）。"""


def healthz(client):
    return client.get("/healthz")


def healthz_probe(client):
    return client.get("/healthz?probe=1")


def proxy_action(client, action, payload=None, token=None):
    body = {"action": action, "payload": payload or {}}
    if token:
        body["token"] = token
    return client.post("/", body)
