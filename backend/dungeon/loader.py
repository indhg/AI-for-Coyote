# -*- coding: utf-8 -*-
"""主题包加载器：manifest + theme + events + bindings → 运行时索引。

复用 M1 的 story_pack 校验（fail-closed：校验不通过拒绝加载）。
"""
from __future__ import annotations

from pathlib import Path

import yaml

from ..story_pack.validator import validate_pack, KIND_THEME_PACK


class PackLoadError(Exception):
    """主题包加载失败（结构/校验错误）。"""


def _read_yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise PackLoadError(f"{path.name} 顶层必须是映射")
    return data


def _yaml_files(dir_path: Path) -> list[Path]:
    return sorted(list(dir_path.glob("*.yaml")) + list(dir_path.glob("*.yml")))


class ThemePack:
    """一个主题内容包（theme pack）的运行时视图。"""

    def __init__(self, pack_dir: Path):
        self.pack_dir = Path(pack_dir)
        if not self.pack_dir.is_dir():
            raise PackLoadError(f"主题包目录不存在：{self.pack_dir}")

        res = validate_pack(self.pack_dir)
        if res.kind != KIND_THEME_PACK or not res.ok:
            detail = "；".join(res.errors[:5]) if res.errors else "未知原因"
            raise PackLoadError(f"主题包校验未通过：{detail}")

        self.manifest = _read_yaml(self.pack_dir / "manifest.yaml")
        self.theme = _read_yaml(self.pack_dir / "theme.yaml")

        contributes = self.manifest.get("contributes") or {}
        ev_rel = str(contributes.get("events") or "events").replace("\\", "/").rstrip("/")
        bd_rel = str(contributes.get("bindings") or "bindings").replace("\\", "/").rstrip("/")
        ev_dir = self.pack_dir / ev_rel
        bd_dir = self.pack_dir / bd_rel

        self.events: list[dict] = []
        for f in _yaml_files(ev_dir):
            doc = _read_yaml(f)
            for e in doc.get("events") or []:
                if isinstance(e, dict):
                    self.events.append(e)
        self.bindings: list[dict] = []
        for f in _yaml_files(bd_dir):
            doc = _read_yaml(f)
            for b in doc.get("bindings") or []:
                if isinstance(b, dict):
                    self.bindings.append(b)

        self.event_index: dict[str, dict] = {e["id"]: e for e in self.events}
        self.binding_index: dict[str, dict] = {b["id"]: b for b in self.bindings}
        self.theme_ids: list[str] = [t.get("id") for t in self.manifest.get("themes") or [] if t.get("id")]
        self.entry_ids: list[str] = [
            e["id"] for e in self.events if e.get("trigger", {}).get("type") == "enter"
        ]
        # prompts/dm.md 作为主题圣经（可选，供叙事注入）
        dm_rel = str(contributes.get("prompts") or "prompts").replace("\\", "/").rstrip("/")
        dm = self.pack_dir / dm_rel / "dm.md"
        self.dm_prompt = dm.read_text(encoding="utf-8").strip() if dm.is_file() else ""

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ThemePack {self.manifest.get('id')!r} events={len(self.events)} bindings={len(self.bindings)}>"


def load_pack(pack_dir: Path | str) -> ThemePack:
    """加载并校验一个主题包目录。"""
    return ThemePack(Path(pack_dir))


def load_packs(pack_dirs) -> dict[str, ThemePack]:
    """加载多个主题包，返回 {theme_id: ThemePack}（合并同 id 去重，后加载覆盖）。"""
    out: dict[str, ThemePack] = {}
    for d in pack_dirs:
        pack = load_pack(d)
        for tid in pack.theme_ids:
            out[tid] = pack
    return out
