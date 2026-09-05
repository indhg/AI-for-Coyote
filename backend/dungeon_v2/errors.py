# -*- coding: utf-8 -*-
"""引擎错误：带错误码，str() 为「[code] 中文说明」，main.py 直接 str(exc) 回 400。"""
from __future__ import annotations


class DungeonError(Exception):
    """地牢引擎拒绝/失败。code 为稳定英文错误码，zh/en 为可读说明。"""

    def __init__(self, code: str, zh: str, en: str | None = None) -> None:
        self.code = str(code)
        self.zh = str(zh)
        self.en = str(en) if en else self.zh
        super().__init__(f"[{self.code}] {self.zh}")

    def to_dict(self) -> dict:
        return {"code": self.code, "zh": self.zh, "en": self.en}


class ContentError(DungeonError):
    """内容包/校验错误（fail-closed）。"""

    def __init__(self, zh: str, en: str | None = None) -> None:
        super().__init__("content", zh, en)
