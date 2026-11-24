#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""轮询等待终态（禁止固定 sleep 后直接断言，规则 8）。"""
import time


def wait_until(fn, timeout=15.0, interval=0.5, message="条件未在超时内满足"):
    end = time.time() + timeout
    last = None
    while time.time() < end:
        try:
            last = fn()
            if last:
                return last
        except Exception as ex:  # 轮询期的临时异常不直接判失败
            last = ex
        time.sleep(interval)
    raise AssertionError(f"{message}（last={last!r}, timeout={timeout}s)")
