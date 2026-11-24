#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""临时 Node 实例（mock 微信 / getOpenid）：独立端口、独立日志、退出即清理。"""
import os
import socket
import subprocess
import time
from pathlib import Path

CF_ROOT = Path(__file__).resolve().parents[3] / "05_代码" / "cloud-functions"
EVID_DIR = Path(__file__).resolve().parents[2] / "evidence"


def wait_port(port, timeout=12.0):
    end = time.time() + timeout
    while time.time() < end:
        with socket.socket() as sock:
            sock.settimeout(0.5)
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                return True
        time.sleep(0.3)
    return False


class NodeProc:
    def __init__(self, name, script, port, env_extra=None):
        self.name = name
        self.script = script
        self.port = port
        self.env_extra = env_extra or {}
        self.proc = None
        self.log_path = EVID_DIR / (name + ".log")

    def start(self, wait=True, timeout=12.0):
        EVID_DIR.mkdir(parents=True, exist_ok=True)
        env = dict(os.environ)
        env.update(self.env_extra)
        node = os.environ.get("NODE_BIN") or "node"
        fh = open(self.log_path, "wb")
        self.proc = subprocess.Popen([node, "--max-old-space-size=256", self.script],
                                     cwd=str(CF_ROOT), env=env, stdout=fh, stderr=subprocess.STDOUT)
        fh.close()
        return wait_port(self.port, timeout) if wait else True

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self.proc = None

    def __enter__(self):
        assert self.start(), f"{self.name} 未在超时内就绪，见 {self.log_path}"
        return self

    def __exit__(self, *args):
        self.stop()
