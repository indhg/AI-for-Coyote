# -*- coding: utf-8 -*-
"""存档：JSON，含 format 标记 + seed + rng_state（D2 §3.4）。

目录：<project_root>/data/saves/dungeon_v2/<slot>.json（与旧引擎 data/saves/dungeon/ 分开）。
旧引擎存档（无 format 标记）直接拒绝：提示新开档，无迁移。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from . import constants as C
from .errors import DungeonError

_SLOT = re.compile(r"^[A-Za-z0-9_\-]{1,40}$")


def save_dir(project_root: Path) -> Path:
    return Path(project_root) / "data" / "saves" / "dungeon_v2"


def save_path(project_root: Path, slot: str) -> Path:
    slot = str(slot or "autosave").strip()
    if not _SLOT.match(slot):
        raise DungeonError("bad_slot", f"存档槽名非法：{slot!r}（只允许字母/数字/_/-，≤40）", f"bad slot name {slot!r}")
    return save_dir(project_root) / f"{slot}.json"


def write_save(path: Path, run_payload: dict) -> str:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = {"format": C.SAVE_FORMAT, "version": C.SAVE_VERSION, **run_payload}
    if "seed" not in doc or "rng_state" not in doc:
        raise DungeonError("save_incomplete", "存档缺 seed/rng_state（引擎 bug）")
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)
    return str(path)


def read_save(path: Path) -> dict:
    path = Path(path)
    if not path.exists():
        raise DungeonError("save_missing", f"存档不存在：{path.name}", f"save not found: {path.name}")
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DungeonError("save_corrupt", f"存档不是合法 JSON：{exc}") from exc
    if not isinstance(doc, dict) or doc.get("format") != C.SAVE_FORMAT:
        raise DungeonError(
            "save_format",
            "该存档不是新引擎格式（旧紫金地牢存档不受支持），请新开一局",
            "save is not a dungeon_v2 save (legacy saves unsupported); start a new run",
        )
    ver = int(doc.get("version", 0))
    accepted = getattr(C, "SAVE_VERSIONS_READ", (C.SAVE_VERSION,))
    if ver not in accepted:
        raise DungeonError("save_version", f"存档版本 {doc.get('version')} 不在可读范围 {accepted}（引擎写 {C.SAVE_VERSION}）")
    for k in ("seed", "rng_state", "pack_id", "run"):
        if k not in doc:
            raise DungeonError("save_corrupt", f"存档缺字段 {k}")
    return doc
