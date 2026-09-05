# -*- coding: utf-8 -*-
"""后端 → UI 字符串的英文版（按协作交接结论 T051 §1.5 / §4.1–4.3 落地）。

中文 UI 模式（lang=zh）走原有 f-string，此模块只在 lang=en 时被调用，
保证聊天动作芯片（▶/✖）、地牢执行反馈等 Python 产出字符串也显示英文。

波形显示名按 §1.6：内部 preset 键（中文）不动，只把发给玩家的展示名换成英文。
"""
from __future__ import annotations

import re

__all__ = ["WAVE_EN", "describe_en", "reason_en", "hint_en"]

# §1.6 波形显示名（preset 中文键 → 英文展示名；未收录的自定义波形原样返回）
WAVE_EN: dict[str, str] = {
    "经典波形": "Classic",
    "挤压": "Squeeze",
    "气泡": "Bubble",
    "律动": "Rhythm",
    "电波": "Airwave",
    "舞步": "Dance",
    "攀登": "Climb",
    "树荫": "Shade",
    "脉冲": "Pulse",
    "呼吸": "Breath",
    "潮汐": "Tide",
    "连击": "Combo",
    "快速按捏": "Rapid Pinch",
    "按捏渐强": "Rising Pinch",
    "心跳节奏": "Heartbeat",
    "压缩": "Compress",
    "节奏步伐": "Cadence",
    "颗粒摩擦": "Grain",
    "渐变弹跳": "Bounce",
    "波浪涟漪": "Ripple",
    "雨水冲刷": "Rain",
    "变速敲击": "Knock",
    "信号灯": "Signal",
    "挑逗1": "Tease 1",
    "挑逗2": "Tease 2",
}


def _wave(p: str) -> str:
    return WAVE_EN.get(p, p)


# ---------- 4.1 _describe 的英文版（game_loop.py / dungeon_v2 体感共用） ----------
def describe_en(cmd: dict) -> str:
    """按 §1.5 显示名模板生成英文执行说明。cmd 为已过安全层的内部命令。"""
    kind = cmd.get("kind")
    ch = cmd.get("channel")
    if kind == "temp":
        return f"{ch} burst {cmd.get('value')} × {cmd.get('duration_s', 0):.1f}s"
    if kind == "hold":
        return f"{ch} hold {cmd.get('value')}"
    if kind == "add":
        return f"{ch} {cmd.get('delta', 0):+d}"
    if kind == "pulse":
        return f"{ch} {_wave(str(cmd.get('pattern') or ''))} × {cmd.get('duration_s', 0):.1f}s"
    if kind == "pulse_hold":
        return f"{ch} {_wave(str(cmd.get('pattern') or ''))} loop"
    if kind == "clear":
        return "clear all" if ch is None else f"clear {ch}"
    if kind == "stop":
        return "zero all"
    return "E-Stop"


# ---------- 4.2 安全层 reason 的英文版（进 ✖ 芯片） ----------
_UNKNOWN_OP = re.compile(r"未知 op: (.+)$")
_ENABLED_OFF = re.compile(r"([AB]) 通道已手动关闭，拒绝动作")
_TEMP = re.compile(r"([AB]) 通道临时强度 (\d+)（上限 (\d+)），持续 ([\d.]+)s")
_HOLD = re.compile(r"([AB]) 通道持续强度 (\d+)（上限 (\d+)，保持到清除）")
_ADD = re.compile(r"([AB]) 通道增减 ([+-]?\d+)（当前 (\d+) -> (\d+)）")
_UNKNOWN_WAVE = re.compile(r"未知波形 (.+?)（可用：(.+?)…）")
_PULSE = re.compile(r"([AB]) 通道波形「(.+?)」\((.+?)\)，([\d.]+)s")
_PULSE_HOLD = re.compile(r"([AB]) 通道持续波形「(.+?)」\((.+?)\)，循环到清除")
_CLEAR_CH = re.compile(r"清除 ([AB]) 通道")
_BAD_CHANNEL = re.compile(r"非法通道: (.+?)（只允许 A/B）")


def reason_en(zh: str) -> str:
    """把安全层产出的中文 reason 翻译成英文（模板与 §4.2 对齐）。"""
    if not zh:
        return zh
    m = _UNKNOWN_OP.search(zh)
    if m:
        return "unknown op: " + m.group(1).strip("'\"")
    m = _ENABLED_OFF.search(zh)
    if m:
        return f"channel {m.group(1)} is off"
    m = _TEMP.search(zh)
    if m:
        return f"{m.group(1)} burst {m.group(2)} (cap {m.group(3)}), {m.group(4)}s"
    m = _HOLD.search(zh)
    if m:
        return f"{m.group(1)} hold {m.group(2)} (cap {m.group(3)})"
    m = _ADD.search(zh)
    if m:
        return f"{m.group(1)} {m.group(2)} ({m.group(3)} → {m.group(4)})"
    m = _UNKNOWN_WAVE.search(zh)
    if m:
        known = " / ".join(_wave(x) for x in m.group(2).split("、"))
        return (
            f"unknown wave {_wave(m.group(1).strip(chr(39) + chr(34)))} "
            f"(have: {known}…)"
        )
    m = _PULSE.search(zh)
    if m:
        return (
            f"{m.group(1)} {_wave(m.group(2))} ({m.group(3)}), "
            f"{m.group(4)}s"
        )
    m = _PULSE_HOLD.search(zh)
    if m:
        return f"{m.group(1)} {_wave(m.group(2))} ({m.group(3)}) loop"
    if zh == "清除全部":
        return "clear all"
    m = _CLEAR_CH.search(zh)
    if m:
        return f"clear {m.group(1)}"
    m = _BAD_CHANNEL.search(zh)
    if m:
        return "bad channel: " + m.group(1).strip("'\"") + " (A/B only)"
    simple = {
        "动作必须是 JSON 对象": "action must be a JSON object",
        "动作必须是对象": "action must be an object",
        "急停中，拒绝一切设备动作": "E-Stop is on, no device commands",
        "全部清零并清除": "zeroed and cleared",
        "设备未连接（无 clientId/slotId）": "device not connected",
        "未知错误": "unknown error",
        "未知 op": "unknown op",
    }
    return simple.get(zh, zh)


# ---------- 4.3 地牢 hint ----------
_HINT_EN = {"无": "none", "轻微": "light", "持续": "steady", "已清理": "cleared", "试探": "tease", "连击": "combo", "停顿": "pause", "清理": "cleared"}


def hint_en(hint: str) -> str:
    return _HINT_EN.get(hint, hint)
