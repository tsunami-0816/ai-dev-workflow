#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pytest 根 conftest：把 qa-automation 加进 sys.path，供 `common/` `api/` 导入。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
