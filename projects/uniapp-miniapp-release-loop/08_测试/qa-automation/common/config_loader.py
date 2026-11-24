#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""配置加载：config.yaml + 环境变量覆盖（MYSQL_PORT/BASE_URL/CF_URL 优先）。"""
import os
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def load_config():
    with open(ROOT / "config" / "config.yaml", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    cfg["base_url"] = os.environ.get("BASE_URL", cfg["base_url"]).rstrip("/")
    cfg["cf_url"] = os.environ.get("CF_URL", cfg["cf_url"]).rstrip("/")
    cfg["h5_url"] = os.environ.get("H5_URL", cfg["h5_url"]).rstrip("/")
    cfg["mysql"]["port"] = int(os.environ.get("MYSQL_PORT", cfg["mysql"]["port"]))
    cfg["mysql"]["password"] = os.environ.get("MYSQL_PASSWORD", cfg["mysql"]["password"])
    return cfg
