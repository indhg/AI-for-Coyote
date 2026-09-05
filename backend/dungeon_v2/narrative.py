# -*- coding: utf-8 -*-
"""叙事文本：seed 基底 + variants 按 SHA-256 稳定哈希轮转（D2 §4.3 / S3 §八）。

variants 为字符串列表；未写/空 = 单版（N=1，恒选基底）。
index 0 → seed（基底 v1）；index k≥1 → variants[k-1]（v2/v3…）。
AI 扩写（cfg.dungeon.ai_narrative）首批不接：source 恒为 seed/variant。
"""
from __future__ import annotations

from .rng import variant_index


def variant_count(event: dict) -> int:
    vs = event.get("variants")
    if isinstance(vs, list) and vs:
        return 1 + len(vs)
    return 1


def select_variant(master_seed: int, event: dict, visit_n: int) -> dict:
    """返回 {"index", "count", "text", "source"}。"""
    n = variant_count(event)
    idx = variant_index(master_seed, str(event["id"]), visit_n, n)
    if idx == 0:
        text, source = str(event["seed"]), "seed"
    else:
        text, source = str(event["variants"][idx - 1]), "variant"
    return {"index": idx, "count": n, "text": text, "source": source}


def compose_text(event: dict, variant: dict, prefix: str | None = None) -> str:
    """把（上一场 exit 一句）+ trigger + 正文拼成一段给前端的叙事。"""
    parts: list[str] = []
    if prefix:
        parts.append(str(prefix))
    trig = str(event.get("trigger") or "").strip()
    if trig:
        parts.append(trig)
    parts.append(variant["text"])
    return "\n".join(p for p in parts if p)
