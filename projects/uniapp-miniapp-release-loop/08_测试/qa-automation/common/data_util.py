#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试数据工具：手机号生成、幂等键复算、脱敏、日期窗口。"""
import hashlib
import random
import time
from datetime import date, timedelta

_seed = random.Random(int(time.time()) % 100000)
_counter = _seed.randint(10000000, 80000000)


def next_phone():
    """生成 11 位、1[3-9] 开头的唯一手机号（139 段 + 8 位序号）。"""
    global _counter
    _counter += 1
    if _counter > 99999999:
        _counter = 10000000
    return "139" + f"{_counter:08d}"


def idem_key(contact, book_date, slot):
    """与 BookingService.idemKey 同口径：ub:idem:booking:{sha256(phone|date|slot)[:32]}。"""
    raw = f"{contact}|{book_date}|{slot}"
    return "ub:idem:booking:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def mask(phone):
    return phone[:3] + "****" + phone[-4:] if len(phone) >= 7 else phone


def days_from_today(n):
    return (date.today() + timedelta(days=n)).isoformat()


def today():
    return date.today().isoformat()
