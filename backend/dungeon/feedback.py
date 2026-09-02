# -*- coding: utf-8 -*-
"""地牢反馈解析（M2 dry_run）：事件 feedback 引用 → 绑定表 → op 动作 + 三态氛围提示。

M2 只「查表 + 三态提示」，不做 SafetyManager 校验与真机执行（那是 M3）。
三态提示不暴露具体强度/波形数值（对齐「设备反馈细节不暴露给玩家」）。
"""
from __future__ import annotations

# op → 三态归类
_CONTINUOUS_OPS = {"hold_strength", "pulse_hold"}
_LIGHT_OPS = {"pulse", "temp_strength", "add_strength"}


def _hint_from_actions(actions: list[dict]) -> str:
    if not actions:
        return "无"
    ops = {a.get("op") for a in actions if isinstance(a, dict)}
    if ops & _CONTINUOUS_OPS:
        return "持续"
    if ops & _LIGHT_OPS:
        return "轻微"
    return "轻微"


def resolve_feedback(event: dict, bindings: dict[str, dict]) -> dict:
    """解析一个事件的设备反馈，返回 {on_enter, on_exit, hint}。

    - on_enter / on_exit：查绑定表得到的 op 动作列表（dry_run 只返回，不执行）。
    - 绑定缺失 → 忽略（fail-closed，不猜）。
    """
    fb = event.get("feedback") or {}
    on_enter_refs = fb.get("on_enter") or []
    on_exit_refs = fb.get("on_exit") or []

    def _expand(refs):
        acts = []
        for ref in refs:
            b = bindings.get(ref)
            if not b:
                continue
            for a in b.get("actions") or []:
                if isinstance(a, dict):
                    acts.append(a)
        return acts

    on_enter = _expand(on_enter_refs)
    on_exit = _expand(on_exit_refs)
    # 事件卡提示按「当前进场反馈」归类（无/轻微/持续）；「已清理」是离开/急停/断开的过渡态，不在这里表达
    hint = _hint_from_actions(on_enter)
    return {"on_enter": on_enter, "on_exit": on_exit, "hint": hint}
