# -*- coding: utf-8 -*-
"""HTTP render 结构（D2 §3.2，字段可加不可删改）：

{"run": {...}, "event": {id,title,theme_id,kind,content_level,tier,choices[{id,label}],free_input},
 "narrative": {"text","source"} | None, "feedback": {"hint"}, "executed": [...], "dropped": [...],
 "map": {...}, "outcome": {...} | None, "theme_labels": {...}}

D11 增补（只加）：choices[].unmet[{key,need,current,text}]；outcome.effective_label；
theme_labels{bands,rooms,mark_stage,ma_tier,feedback,endings,dice{name,desc}}（按 en 切）；run.dice_name/dice_desc 按 en 切。

映射：theme_id = 包 id；content_level ← intensity（none0/low1/medium2/medium-high3/high4）；
tier ← band（entry1/mid2/upper3/lower4/end5）。
"""
from __future__ import annotations

from . import constants as C
from .engine import Engine, Outcome, Run
from .feedback import hint_text
from .loader import Pack
from .narrative import compose_text
from .map_logic import render_map


def event_view(pack: Pack, engine: Engine, run: Run, event: dict) -> dict:
    gates = engine.choice_gate_view(run, event)
    choices = []
    for i, ch in enumerate(event.get("choices") or []):
        g = gates[i]
        item = {
            "id": str(i + 1),
            "label": str(ch["label"]),
            "settlement": str(ch["settlement"]),
            "disabled": g["disabled"],
        }
        if g["disabled_reason"]:
            item["disabled_reason"] = g["disabled_reason"]
        if g.get("unmet"):
            item["unmet"] = list(g["unmet"])
        if g["check"]:
            item["check"] = g["check"]
        if g["gates"]:
            item["require"] = g["gates"]
        if ch.get("estop_overrides"):
            item["estop_overrides"] = True
        choices.append(item)
    locked = run.phase in ("ended", "locked")
    return {
        "id": str(event["id"]),
        "title": str(event["title"]),
        "theme_id": pack.id,
        "kind": str(event["kind"]),
        "content_level": C.CONTENT_LEVEL_BY_INTENSITY.get(str(event["intensity"]), 0),
        "tier": C.TIER_BY_BAND.get(str(event["band"]), 1),
        "choices": [] if locked else choices,
        "free_input": False,
        # 新增字段（可加）
        "band": str(event["band"]),
        "room": str(event["room"]),
        "intensity": str(event["intensity"]),
        "species": str(event.get("species", C.SPECIES_NONE)),
        "settlement": list(event.get("settlement") or []),
        "checks": list(event.get("checks") or []),
        "visit_n": run.visit_n,
        "variant": {"index": run.variant.get("index", 0), "count": run.variant.get("count", 1)},
        "feedback_raw": str(event.get("feedback", "")),
    }


def feedback_view(cores: list[str], en: bool, pack: Pack) -> dict:
    labels = pack.theme.get("feedback_labels") or {}
    primary = cores[-1] if cores else "无"
    return {
        "hint": hint_text(primary, en),
        "cores": [hint_text(c, en) for c in cores],
        "label": str(labels.get(primary, primary)),
    }


def outcome_view(out: Outcome | None) -> dict | None:
    if out is None:
        return None
    return {
        "event": out.event_before,
        "choice": out.choice_index,
        "label": out.choice_label,
        "effective_choice": out.effective_index,
        "effective_label": out.effective_label,
        "settlement": out.settlement,
        "check": out.check,
        "folded": out.folded,
        "effects": out.effects.get("applied", []),
        "skipped": out.effects.get("skipped", []),
        "dice_gain": out.effects.get("dice_gain"),
        "defeat": out.defeat,
        "gate_checked": out.gate_checked,
        "crossed": out.crossed,
        "ending": out.ending,
        "next_event": out.next_event,
        "exit": out.exit_text,
        "estop_overrides": out.estop_overrides,
    }


def theme_labels_view(pack: Pack, en: bool) -> dict:
    """主题显示名（D11 E3）：来自 theme.json；骰子名/描述来自 constants 按 en 切。前端优先读这里，本地表只作回退。"""
    th = pack.theme or {}
    return {
        "bands": dict(th.get("bands") or {}),
        "rooms": dict(th.get("rooms") or {}),
        "mark_stage": dict(th.get("mark_stage_labels") or {}),
        "ma_tier": dict(th.get("ma_tier_labels") or {}),
        "feedback": dict(th.get("feedback_labels") or {}),
        "endings": dict(th.get("ending_labels") or {}),
        "dice": {
            "name": dict(C.DICE_NAME_EN if en else C.DICE_NAME_ZH),
            "desc": dict(C.DICE_DESC_EN if en else C.DICE_DESC_ZH),
        },
    }


def map_view(pack: Pack, run: Run) -> dict:
    """chain：轻量剖面；map：§6.1 路网契约。"""
    if getattr(run, "mode", "chain") == "map" and run.map:
        return render_map(run.map, run.state, phase=run.phase)
    nodes = []
    for eid, ev in pack.events.items():
        nodes.append({
            "id": eid, "title": str(ev["title"]), "band": str(ev["band"]), "room": str(ev["room"]),
            "visited": int(run.visits.get(eid, 0)), "current": eid == run.event_id,
        })
    return {"mode": "chain", "current": run.event_id, "nodes": nodes}


def build(pack: Pack, engine: Engine, run: Run, *, executed: list, dropped: list,
          cores: list[str], en: bool, outcome: Outcome | None = None) -> dict:
    event = engine.current_event(run)
    text = compose_text(event, run.variant, prefix=run.last_exit)
    if outcome is not None and outcome.ending:
        # 结局：正文 = 该结局 choice 的 exit 句（已清理设备，锁定/结束）
        text = outcome.exit_text or text
    return {
        "run": run.snapshot(en=en),
        "event": event_view(pack, engine, run, event),
        "narrative": {"text": text, "source": str(run.variant.get("source", "seed")) if not (outcome and outcome.ending) else "ending"},
        "feedback": feedback_view(cores, en, pack),
        "executed": list(executed),
        "dropped": list(dropped),
        "map": map_view(pack, run),
        "outcome": outcome_view(outcome),
        "theme_labels": theme_labels_view(pack, en),
    }
