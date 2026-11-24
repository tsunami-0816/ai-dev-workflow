#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""健康检查封装。"""


def health(client):
    return client.get("/actuator/health")


def healthz_cf(client):
    return client.get("/healthz")
