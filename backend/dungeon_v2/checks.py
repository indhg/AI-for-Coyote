# -*- coding: utf-8 -*-
"""属性检定（S1 §三 / S3 §四 / S4）：attr + 骰子加成(0~N) >= TN。

骰子来源 = run RNG（与装配同源，state 入档）。
    d1 : 0/1        d4 : 0~4        d6 : 0~6
    ed6: 先掷 0~6，再独立掷归零判定（15%）→ 归零时最终输出整体为 0（必失败）
RNG 消费顺序固定：先 randint(0, N)，ed6 再 random() 判归零。
"""
from __future__ import annotations

from . import constants as C
from .rng import RunRNG
from .state import RunState


def roll_bonus(rng: RunRNG, dice: str) -> dict:
    """掷装备骰。返回 {dice, raw, zeroed, bonus}。"""
    if dice not in C.DICE_MAX_BONUS:
        dice = C.DEFAULT_DICE
    raw = rng.randint(0, C.DICE_MAX_BONUS[dice])
    zeroed = False
    if dice == "ed6":
        zeroed = rng.random() < (C.ED6_ZERO_PCT / 100.0)
    return {"dice": dice, "raw": raw, "zeroed": zeroed, "bonus": raw}


def resolve_check(state: RunState, rng: RunRNG, attr: str, tn: int) -> dict:
    """执行一次属性检定，返回记录（进 run.log）。

    total = attr + bonus；ed6 归零 → total = 0（整结果归零，必失败）。
    """
    attr_value = state.attr(attr)
    roll = roll_bonus(rng, state.dice)
    total = 0 if roll["zeroed"] else attr_value + roll["bonus"]
    return {
        "attr": attr,
        "tn": int(tn),
        "attr_value": attr_value,
        "dice": roll["dice"],
        "raw": roll["raw"],
        "zeroed": roll["zeroed"],
        "bonus": roll["bonus"],
        "total": total,
        "success": total >= int(tn),
    }


def split_require(require: dict | None) -> tuple[tuple[str, int] | None, dict]:
    """把 require 拆成 (属性检定 (attr, TN) | None, 门槛 dict)。validator 保证最多一个属性键。"""
    require = dict(require or {})
    attr_check = None
    gates = {}
    for k, v in require.items():
        if k in C.REQUIRE_ATTR_KEYS:
            attr_check = (k, int(v))
        else:
            gates[k] = v
    return attr_check, gates


def unmet_gates_struct(state: RunState, gates: dict) -> list[dict]:
    """结构化未满足门槛（D11 E2）：[{key, need, current, text}]，空 = 全部满足。

    key = require 键（stage_min / yin_hua_gte / ma_gte …），need = 门槛值，current = 当前值；
    text = 中文说明（向后兼容旧 disabled_reason / require_unmet 文案）。前端按 key 自拼文案。
    """
    unmet: list[dict] = []
    for k, v in gates.items():
        if k == "stage_min":
            if not state.stage_at_least(str(v)):
                unmet.append({"key": k, "need": str(v), "current": state.mark_stage,
                              "text": f"淫纹需至少 {v}（当前 {state.mark_stage}）"})
        elif k.endswith("_gte"):
            field = k[:-4]
            cur = state.attr(field)
            if cur < int(v):
                unmet.append({"key": k, "need": int(v), "current": cur,
                              "text": f"{field} 需 ≥ {v}（当前 {cur}）"})
        else:
            unmet.append({"key": k, "need": v, "current": None, "text": f"未知门槛 {k}"})
    return unmet


def unmet_gates(state: RunState, gates: dict) -> list[str]:
    """返回未满足的门槛说明列表（空 = 全部满足）。= unmet_gates_struct 的 text 投影。"""
    return [u["text"] for u in unmet_gates_struct(state, gates)]
