#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""套餐接口封装。"""


def packages(client, page=None, size=None):
    params = []
    if page is not None:
        params.append(f"page={page}")
    if size is not None:
        params.append(f"size={size}")
    path = "/api/packages" + (("?" + "&".join(params)) if params else "")
    return client.get(path)


def package_detail(client, pkg_id):
    return client.get(f"/api/packages/{pkg_id}")
