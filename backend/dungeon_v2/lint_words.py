# -*- coding: utf-8 -*-
"""禁词扫描（验收 §七.6）：事件 seed / variants / trigger / title / note / feedback / choices(label,exit,note)
/ flags 说明 / theme 标签 / bindings 说明 / base_setting / 引擎自带 EN 文案。

用法：python -m backend.dungeon_v2.lint_words <pack_dir> [--extra-en]
退出码：0 = 0 泄漏；1 = 有泄漏；2 = 包读不出来。

D18 词表调整（2026-09-04 用户拍板，S2 §四 用语表同步）：
  放行氛围词——「血」字氛围用法（血迹/鲜血/充血/血梯/血瀑布…非伤害描写）、「装备」「经验」的非系统化提及，
  三词从 GLOBAL_ZH 移除；「血腥」作为伤害/红线类单独保留（原先由「血」子串覆盖）。
  仍卡：血腥/撕裂/内脏/真孕/未成年/幼体/分娩/斩首/尸体/d20/金币/职业 + 全部设备词/通道字母/波形名。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from . import constants as C

# 设备硬件词（中文，子串匹配）
DEVICE_ZH = ("贴片", "肛塞", "通道", "电极", "波形", "脉冲", "电击", "电流", "电停", "郊狼", "强度值")
# 设备硬件词（英文，词边界、不分大小写）
DEVICE_EN = ("patch", "plug", "channel", "electrode", "waveform", "estim", "e-stim", "shock")
# 通道字母 / 数字泄漏
CHANNEL_PATTERNS = (re.compile(r"[AB]\s*通道"), re.compile(r"通道\s*[AB]"), re.compile(r"\bA/B\b"))
# 全局禁词（S2 §四 + 铁律）。D18：移除「血」「经验」「装备」（氛围放行），加「血腥」（伤害类仍卡）
GLOBAL_ZH = (
    "未成年", "幼体", "分娩", "真孕", "撕裂", "内脏", "血腥", "斩首", "尸体",
    "d20", "金币", "职业",
    "校园", "宿舍", "学姐", "警械", "都市", "紫液", "魔物娘", "史莱姆娘", "龙女", "魅魔娘", "学生",
)
# 波形名里属于普通身体/环境词、叙事允许出现（S1 用语「呼吸」为身体词）
WAVE_NAME_ALLOW = {"呼吸"}
# 只在 feedback 字段允许的核心词（与波形名「连击」同形）
FEEDBACK_ONLY = set(C.FEEDBACK_CORE)


def wave_names() -> set[str]:
    try:
        from ..waveforms import WAVEFORMS  # type: ignore
        return {str(m["cn"]) for m in WAVEFORMS.values() if isinstance(m, dict) and "cn" in m}
    except Exception:  # noqa: BLE001
        return {"挤压", "气泡", "律动", "电波", "舞步", "攀登", "树荫", "脉冲", "呼吸", "潮汐", "连击",
                "快速按捏", "按捏渐强", "心跳节奏", "压缩", "节奏步伐", "颗粒摩擦", "渐变弹跳",
                "波浪涟漪", "雨水冲刷", "变速敲击", "信号灯", "挑逗1", "挑逗2"}


def scan_text(text: str, where: str, field_kind: str = "narrative", waves: set[str] | None = None) -> list[str]:
    """返回该文本的泄漏列表（空 = 干净）。field_kind: narrative / feedback / binding / en。"""
    hits: list[str] = []
    if not isinstance(text, str) or not text:
        return hits
    low = text.lower()
    for w in DEVICE_ZH:
        if w in text:
            hits.append(f"{where}: 设备词「{w}」")
    for w in DEVICE_EN:
        if re.search(rf"(?<![a-z]){re.escape(w)}(?![a-z])", low):
            hits.append(f"{where}: device word '{w}'")
    for p in CHANNEL_PATTERNS:
        if p.search(text):
            hits.append(f"{where}: 通道字母泄漏「{p.pattern}」")
    if field_kind != "binding":  # bindings 的 desc 允许写波形名（它就是绑定说明）
        for w in (waves or wave_names()):
            if w in WAVE_NAME_ALLOW:
                continue
            if field_kind == "feedback" and w in FEEDBACK_ONLY:
                continue
            if w in text:
                hits.append(f"{where}: 波形名「{w}」")
    for w in GLOBAL_ZH:
        if w in text:
            hits.append(f"{where}: 全局禁词「{w}」")
    return hits


def scan_tree(tree: dict) -> list[str]:
    waves = wave_names()
    hits: list[str] = []
    events = tree.get("events") or {}
    for eid, ev in events.items():
        if not isinstance(ev, dict):
            continue
        for k in ("title", "trigger", "seed", "note"):
            hits += scan_text(ev.get(k, ""), f"{eid}.{k}", "narrative", waves)
        hits += scan_text(ev.get("feedback", ""), f"{eid}.feedback", "feedback", waves)
        for i, v in enumerate(ev.get("variants") or []):
            hits += scan_text(v, f"{eid}.variants[{i}]", "narrative", waves)
        for k, v in (ev.get("flags") or {}).items():
            hits += scan_text(v, f"{eid}.flags.{k}", "narrative", waves)
        for i, ch in enumerate(ev.get("choices") or []):
            if not isinstance(ch, dict):
                continue
            for k in ("label", "exit", "note"):
                hits += scan_text(ch.get(k, ""), f"{eid}.choices[{i + 1}].{k}", "narrative", waves)
    theme = tree.get("theme") or {}
    if isinstance(theme, dict):
        for k in ("title", "description"):
            hits += scan_text(theme.get(k, ""), f"theme.{k}", "narrative", waves)
        for grp in ("bands", "feedback_labels"):
            for k, v in (theme.get(grp) or {}).items():
                hits += scan_text(v, f"theme.{grp}.{k}", "feedback" if grp == "feedback_labels" else "narrative", waves)
    b = tree.get("bindings") or {}
    if isinstance(b, dict):
        hits += scan_text(b.get("note", ""), "bindings.note", "binding", waves)
        for core, spec in (b.get("rhythm") or {}).items():
            if isinstance(spec, dict):
                hits += scan_text(spec.get("desc", ""), f"bindings.rhythm[{core}].desc", "binding", waves)
    hits += scan_text(tree.get("base_setting", ""), "base_setting", "narrative", waves)
    return hits


def scan_engine_en() -> list[str]:
    """引擎自带的 EN 展示文案（骰子描述等）。"""
    hits: list[str] = []
    for k, v in C.DICE_DESC_EN.items():
        hits += scan_text(v, f"constants.DICE_DESC_EN[{k}]", "en")
    for k, v in C.DICE_NAME_EN.items():
        hits += scan_text(v, f"constants.DICE_NAME_EN[{k}]", "en")
    for k, v in C.DICE_DESC_ZH.items():
        hits += scan_text(v, f"constants.DICE_DESC_ZH[{k}]", "narrative")
    return hits


def main(argv: list[str] | None = None) -> int:
    from .cli import utf8_console
    utf8_console()
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print(__doc__)
        return 2
    from .loader import load_tree
    try:
        tree = load_tree(Path(argv[0]))
    except Exception as exc:  # noqa: BLE001
        print(f"包读取失败：{exc}")
        return 2
    hits = scan_tree(tree) + scan_engine_en()
    for h in hits:
        print("LEAK", h)
    print(f"禁词扫描：{len(hits)} 处泄漏 → {'OK' if not hits else 'FAIL'}")
    return 0 if not hits else 1


if __name__ == "__main__":
    sys.exit(main())
