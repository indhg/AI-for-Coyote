# -*- coding: utf-8 -*-
"""CLI 公共小工具（D6 R1）：Windows 默认 GBK 控制台下打印非 GBK 字符会 UnicodeEncodeError 崩溃，
所有 `python -m backend.dungeon_v2.*` 入口先把 stdout/stderr 切到 UTF-8（编不出的字符替换成 ?）。
运行链（uvicorn / main.py）不经过这里。
"""
from __future__ import annotations

import sys


def utf8_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:  # noqa: BLE001
                pass
