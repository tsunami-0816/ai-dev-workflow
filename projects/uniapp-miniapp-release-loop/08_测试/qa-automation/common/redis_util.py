#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""最小 Redis RESP 客户端：INFO/GET/DEL/TTL/SCAN/PING，够 L3 断言用，不引第三方依赖。"""
import socket


class Redis:
    def __init__(self, host, port, timeout=5):
        self.host = host
        self.port = port
        self.timeout = timeout

    @staticmethod
    def _encode(args):
        parts = [f"*{len(args)}\r\n".encode()]
        for arg in args:
            raw = str(arg).encode("utf-8")
            parts.append(f"${len(raw)}\r\n".encode() + raw + b"\r\n")
        return b"".join(parts)

    def _read_reply(self, sock):
        line = sock.recv(1)
        if not line:
            raise RuntimeError("redis 连接被关闭")
        if line == b"+":
            return self._read_line(sock)
        if line == b"-":
            raise RuntimeError("redis error: " + self._read_line(sock))
        if line == b":":
            return int(self._read_line(sock))
        if line == b"$":
            length = int(self._read_line(sock))
            if length == -1:
                return None
            data = b""
            while len(data) < length:
                data += sock.recv(length - len(data))
            sock.recv(2)
            return data.decode("utf-8", errors="replace")
        if line == b"*":
            count = int(self._read_line(sock))
            if count == -1:
                return None
            return [self._read_reply(sock) for _ in range(count)]
        raise RuntimeError(f"未知 RESP 前缀 {line!r}")

    @staticmethod
    def _read_line(sock):
        data = b""
        while not data.endswith(b"\r\n"):
            data += sock.recv(1)
        return data[:-2].decode("utf-8", errors="replace")

    def cmd(self, *args):
        with socket.create_connection((self.host, self.port), timeout=self.timeout) as sock:
            sock.sendall(self._encode(args))
            return self._read_reply(sock)

    def ping(self):
        return self.cmd("PING") == "PONG"

    def info(self, section="stats"):
        text = self.cmd("INFO", section)
        result = {}
        for line in (text or "").splitlines():
            if not line or line.startswith("#") or ":" not in line:
                continue
            key, value = line.split(":", 1)
            result[key] = value
        return result

    def get(self, key):
        return self.cmd("GET", key)

    def delete(self, *keys):
        return self.cmd("DEL", *keys)

    def ttl(self, key):
        return self.cmd("TTL", key)
