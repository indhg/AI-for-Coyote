# -*- coding: utf-8 -*-
"""地牢存档：run 快照（含 RNG 状态）→ JSON，可续局。"""
from __future__ import annotations

import json
from pathlib import Path

from .engine import DungeonEngine


def _rng_state_to_json(state):
    # random.getstate() = (version:int, tuple_of_625_ints, gauss_next:None|float)
    version, internal, gauss = state
    return [version, list(internal), gauss]


def _rng_state_from_json(data):
    version, ints, gauss = data
    return (version, tuple(ints), gauss)


def save_run(engine: DungeonEngine, run: dict, save_dir, slot: str = "autosave") -> str:
    """把 run 存成 JSON，返回文件路径。slot: autosave | 1 | 2 | 3。"""
    snap = engine.snapshot(run)
    snap["rng_state"] = _rng_state_to_json(snap["rng_state"])
    d = Path(save_dir)
    path = d / str(run["preset_id"]) / f"{slot}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snap, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def load_run(save_dir, preset_id: str, slot: str = "autosave") -> dict:
    """读档并恢复 run 对象（rng_state 还原为可 setstate 的元组）。"""
    path = Path(save_dir) / preset_id / f"{slot}.json"
    if not path.is_file():
        raise FileNotFoundError(f"存档不存在：{path}")
    snap = json.loads(path.read_text(encoding="utf-8"))
    snap["rng_state"] = _rng_state_from_json(snap["rng_state"])
    return DungeonEngine.restore(snap)
