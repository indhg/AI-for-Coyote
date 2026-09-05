# -*- coding: utf-8 -*-
"""effects grammar 结算（D2 §4.2 / S3 §二、§四、§六）。

grammar：
    单条 dict：{yin_hua: +5, ma: +15, stage_appear: true}
    多条列表：[{ma: +10, visit_n_eq: 1}, {yin_hua: +5}]
每条可带 visit_n_eq: N → 仅本事件本次进入 visit_n == N 时生效。
逐条按序应用 → 调用方全量钳制。stage 指令按写入顺序覆盖。
三维成长 delta（str/dex/int，任意正负）仅 visit_n == 1 生效（S3 §四 防折返刷）。
"""
from __future__ import annotations

from . import constants as C
from .rng import RunRNG
from .state import RunState, stage_index


def normalize_effects(raw) -> list[dict]:
    """把 effects 字段归一为 list[dict]（None/空 → []）。不做合法性检查（validator 负责）。"""
    if raw is None:
        return []
    if isinstance(raw, dict):
        return [dict(raw)]
    if isinstance(raw, list):
        return [dict(x) for x in raw if isinstance(x, dict)]
    return []


def apply_effects(state: RunState, effects, visit_n: int, rng: RunRNG) -> dict:
    """按序应用 effects 到 state（不钳制，调用方随后 state.clamp_all()）。

    返回结算摘要：
        applied  : [{key, value, before, after}]  实际生效的字段变更
        skipped  : [{key, value, reason}]          被跳过的条目（visit_n 门 / 成长门 / 忽略键）
        dice_gain: 新骰子 id 或 None
    """
    summary = {"applied": [], "skipped": [], "dice_gain": None}
    for entry in normalize_effects(effects):
        gate = entry.get("visit_n_eq")
        if gate is not None and int(gate) != int(visit_n):
            summary["skipped"].append(
                {"key": "*", "value": {k: v for k, v in entry.items() if k != "visit_n_eq"},
                 "reason": f"visit_n_eq {gate} != {visit_n}"}
            )
            continue
        for key, value in entry.items():
            if key in C.EFFECT_META_KEYS:
                continue
            if key in C.EFFECT_DELTA_KEYS:
                if key in C.ATTRS and int(visit_n) != 1:
                    summary["skipped"].append({"key": key, "value": value, "reason": "growth_only_first_visit"})
                    continue
                before = state.attr(key)
                setattr(state, key, before + int(value))
                summary["applied"].append({"key": key, "value": int(value), "before": before, "after": state.attr(key)})
            elif key in C.EFFECT_STAGE_KEYS:
                if not value:
                    continue
                before = state.mark_stage
                if key == "stage_down":
                    idx = max(0, stage_index(before) - 1)
                    state.mark_stage = C.MARK_STAGES[idx]
                else:
                    state.mark_stage = C.EFFECT_STAGE_TARGET[key]
                summary["applied"].append({"key": key, "value": True, "before": before, "after": state.mark_stage})
            elif key == "dice_gain":
                if not value:
                    continue
                before = state.dice
                new_dice = rng.choice(list(C.DICE_DROP_POOL))
                state.dice = new_dice
                summary["dice_gain"] = new_dice
                summary["applied"].append({"key": "dice_gain", "value": new_dice, "before": before, "after": new_dice})
            elif key == "ability_up":
                summary["skipped"].append({"key": key, "value": value, "reason": "ability_not_in_first_batch"})
            else:
                summary["skipped"].append({"key": key, "value": value, "reason": "unknown_key"})
    return summary
