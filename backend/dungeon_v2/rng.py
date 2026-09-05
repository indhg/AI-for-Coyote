# -*- coding: utf-8 -*-
"""随机两层（D2 §4.3）。

装配 / 骰子：run PRNG（random.Random，state 可序列化入档）。
表达变体：SHA-256 稳定哈希（禁内置 hash()）。
数值扰动：独立真随机（不入档，见 feedback.py）。
"""
from __future__ import annotations

import hashlib
import os
import random


def variant_index(master_seed: int, event_id: str, visit_n: int, n_variants: int) -> int:
    """跨进程可复现的变体索引。n_variants<=1 恒 0（基底）。"""
    n = int(n_variants)
    if n <= 1:
        return 0
    h = hashlib.sha256(f"{int(master_seed)}|{event_id}|{int(visit_n)}".encode("utf-8")).digest()
    return int.from_bytes(h[:8], "big") % n


def seed_from_any(value) -> int:
    """把 HTTP 传来的 seed（int / 数字串 / 任意串 / None）折成 master seed（非负 int）。"""
    if value is None or value == "":
        return int.from_bytes(os.urandom(8), "big")
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return abs(value)
    s = str(value).strip()
    if s.lstrip("-").isdigit():
        return abs(int(s))
    return int.from_bytes(hashlib.sha256(s.encode("utf-8")).digest()[:8], "big")


class RunRNG:
    """run PRNG 包装：装配 + 骰子同源，state 可 JSON 序列化。"""

    def __init__(self, seed: int) -> None:
        self._r = random.Random(int(seed))

    def randint(self, a: int, b: int) -> int:
        return self._r.randint(a, b)

    def random(self) -> float:
        return self._r.random()

    def choice(self, seq):
        return seq[self._r.randrange(len(seq))]

    # ---- 序列化（Mersenne Twister state: (version, tuple[625 int], gauss_next)） ----
    def get_state(self) -> list:
        version, internal, gauss = self._r.getstate()
        return [int(version), [int(x) for x in internal], gauss]

    def set_state(self, data) -> None:
        if not (isinstance(data, list) and len(data) == 3 and isinstance(data[1], list)):
            raise ValueError("rng_state 格式错误")
        version, internal, gauss = data
        self._r.setstate((int(version), tuple(int(x) for x in internal), gauss))

    @classmethod
    def from_state(cls, data) -> "RunRNG":
        rng = cls(0)
        rng.set_state(data)
        return rng
