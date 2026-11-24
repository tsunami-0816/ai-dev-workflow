#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""鉴权接口封装（L2/L4 共用）。"""
from common.request_util import ApiClient


def login_api(client, account, password):
    return client.post("/api/auth/login", {"account": account, "password": password})


def login_openid(client, openid, nickname=None, extra_headers=None):
    return client.post("/api/auth/login", {"openid": openid, "nickname": nickname},
                       headers=extra_headers)


def logout_api(client):
    return client.post("/api/auth/logout")


def make_client(base_url, token=None, name="api"):
    return ApiClient(base_url, token=token, name=name)
