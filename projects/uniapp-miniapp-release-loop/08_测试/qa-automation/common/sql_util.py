#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MySQL 访问：复用本机 mysql.exe（不额外引依赖），供 L2/L3/L4 做落库断言与清理。"""
import subprocess


class Mysql:
    def __init__(self, cfg):
        self.cfg = cfg
        self.base = [
            cfg["client"], f"--host={cfg['host']}", f"--port={cfg['port']}",
            f"--user={cfg['user']}", f"--password={cfg['password']}",
            "--default-character-set=utf8mb4", "-N", "-B", "-D", cfg["database"],
        ]

    def _run(self, sql):
        out = subprocess.run(self.base + ["-e", sql], capture_output=True, text=True,
                             encoding="utf-8", errors="replace")
        stderr = out.stderr or ""
        # mysql.exe 对 --password 固定打 Warning，不能据此判失败
        if "ERROR" in stderr.upper() or out.returncode not in (0, 1):
            raise RuntimeError(f"mysql 失败: {stderr.strip()} sql={sql[:200]}")
        return out.stdout

    def query(self, sql):
        text = self._run(sql).strip()
        if not text:
            return []
        return [line.split("\t") for line in text.splitlines()]

    def scalar(self, sql, default=None):
        rows = self.query(sql)
        return rows[0][0] if rows else default

    def execute(self, sql):
        self._run(sql)

    @staticmethod
    def quote(value):
        return "'" + str(value).replace("'", "''") + "'"
