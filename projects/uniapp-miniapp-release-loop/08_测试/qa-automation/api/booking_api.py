#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""预约接口封装。"""


def create_booking(client, package_id, book_date, slot, contact, remark=None):
    body = {"packageId": package_id, "bookDate": book_date, "slot": slot, "contact": contact}
    if remark is not None:
        body["remark"] = remark
    return client.post("/api/bookings", body)


def my_bookings(client, page=None, size=None, extra_query=None):
    params = []
    if page is not None:
        params.append(f"page={page}")
    if size is not None:
        params.append(f"size={size}")
    if extra_query:
        params.append(extra_query)
    path = "/api/bookings" + (("?" + "&".join(params)) if params else "")
    return client.get(path)
