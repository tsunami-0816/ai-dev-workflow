#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""RabbitMQ 管理 API：队列深度/累计发布/重投/清空（仅测试用）。"""
import base64
import json
import urllib.parse
import urllib.request


class Mq:
    def __init__(self, cfg):
        self.url = cfg["mgmt_url"]
        self.auth = "Basic " + base64.b64encode(f"{cfg['user']}:{cfg['password']}".encode()).decode()
        self.cfg = cfg

    def _req(self, method, path, payload=None):
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = urllib.request.Request(self.url + path, data=data, method=method,
                                     headers={"Authorization": self.auth,
                                              "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            text = resp.read().decode("utf-8")
            return json.loads(text) if text else None

    def queue(self, name):
        return self._req("GET", "/queues/%2F/" + urllib.parse.quote(name))

    def depth(self, name):
        return self.queue(name).get("messages", 0)

    def publish_count(self, name):
        return self.queue(name).get("message_stats", {}).get("publish", 0)

    def publish_raw(self, payload, routing_key=None, props=None):
        body = {
            "properties": props or {"content_type": "application/json",
                                    "__TypeId__": "com.uniapp.booking.mq.BookingCreatedEvent"},
            "routing_key": routing_key or self.cfg["routing_key"],
            "payload": payload,
            "payload_encoding": "string",
        }
        return self._req("POST", "/exchanges/%2F/" + urllib.parse.quote(self.cfg["exchange"]) + "/publish", body)

    def purge(self, name):
        return self._req("DELETE", "/queues/%2F/" + urllib.parse.quote(name) + "/contents")
