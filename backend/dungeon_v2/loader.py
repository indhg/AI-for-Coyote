# -*- coding: utf-8 -*-
"""主题包加载（fail-closed）。

包目录结构（content/pack/dungeon/<pack_id>/）：
    manifest.json        format=dungeon_v2 / id / title / themes / start_event / safe_room / 文件指针
    theme.json           主题说明 + 层带/反馈标签
    events/E0xx.json     事件（文件名 stem 必须等于 id）
    bindings.json        feedback 核心词 → 设备动作模板（数字只在这里，不进叙事）
    base_setting.md      世界观底稿（给叙事/审核看；LLM 扩写首批不启用）

任何校验 error → 整包拒绝（ContentError）。旧格式目录（无 manifest.json 或 format 不符）静默跳过。
支持 .json（首选）与 .yaml/.yml（有 PyYAML 时）。
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from . import constants as C
from .errors import ContentError, DungeonError
from .schema import ValidationResult, validate_tree

logger = logging.getLogger("ai-for-coyote.dungeon_v2.loader")

try:  # PyYAML 在 requirements 里，但保持可选
    import yaml as _yaml
except Exception:  # noqa: BLE001
    _yaml = None


def _read_data(path: Path):
    text = path.read_text(encoding="utf-8-sig")
    if path.suffix.lower() == ".json":
        return json.loads(text)
    if path.suffix.lower() in (".yaml", ".yml"):
        if _yaml is None:
            raise ContentError(f"{path.name} 是 YAML 但未安装 PyYAML")
        return _yaml.safe_load(text)
    raise ContentError(f"不支持的文件类型 {path.name}")


def known_patterns_default() -> set[str] | None:
    """波形名单（bindings.pattern 引用）：来自 backend/waveforms.py 的中文名。取不到时返回 None（校验降级为不查）。"""
    try:
        from ..waveforms import WAVEFORMS  # type: ignore
    except Exception:  # noqa: BLE001
        return None
    return {str(meta["cn"]) for meta in WAVEFORMS.values() if isinstance(meta, dict) and "cn" in meta}


@dataclass
class Pack:
    root: Path
    manifest: dict
    theme: dict
    events: dict
    bindings: dict
    base_setting: str
    validation: ValidationResult = field(default_factory=ValidationResult)

    @property
    def id(self) -> str:
        return str(self.manifest["id"])

    @property
    def title(self) -> str:
        return str(self.manifest["title"])

    @property
    def themes(self) -> list[str]:
        return [str(t) for t in self.manifest.get("themes") or [self.id]]

    @property
    def start_event(self) -> str:
        return str(self.manifest["start_event"])

    @property
    def safe_room(self) -> str:
        return str(self.manifest["safe_room"])

    @property
    def mode(self) -> str:
        m = str(self.manifest.get("mode") or C.PACK_MODE_CHAIN).lower()
        return C.PACK_MODE_MAP if m == C.PACK_MODE_MAP else C.PACK_MODE_CHAIN

    def event(self, eid: str) -> dict:
        ev = self.events.get(eid)
        if ev is None:
            raise DungeonError("event_missing", f"事件 {eid} 不存在于包 {self.id}", f"event {eid} missing in pack {self.id}")
        return ev

    def summary(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "description": str((self.theme or {}).get("description", "")),
            "themes": self.themes,
            "event_count": len(self.events),
            "version": str(self.manifest.get("version", "")),
            "engine": C.PACK_FORMAT,
            "mode": self.mode,
        }


def load_tree(root: Path) -> dict:
    """读包目录成内存树（不校验语义；文件缺失/JSON 坏 → ContentError）。"""
    root = Path(root)
    mpath = root / "manifest.json"
    if not mpath.exists():
        raise ContentError(f"{root} 缺少 manifest.json")
    try:
        manifest = _read_data(mpath)
    except json.JSONDecodeError as exc:
        raise ContentError(f"manifest.json 不是合法 JSON：{exc}") from exc
    if not isinstance(manifest, dict):
        raise ContentError("manifest.json 必须是 JSON 对象")

    def _sub(key: str, default: str) -> Path:
        return root / str(manifest.get(key) or default)

    events_dir = _sub("events_dir", "events")
    events: dict[str, dict] = {}
    if not events_dir.is_dir():
        raise ContentError(f"事件目录不存在：{events_dir}")
    for p in sorted(events_dir.iterdir()):
        if p.suffix.lower() not in (".json", ".yaml", ".yml") or p.name.startswith("_"):
            continue
        try:
            data = _read_data(p)
        except json.JSONDecodeError as exc:
            raise ContentError(f"{p.name} 不是合法 JSON：{exc}") from exc
        key = p.stem
        if key in events:
            raise ContentError(f"事件 {key} 重复（json/yaml 同名）")
        events[key] = data

    tree = {"manifest": manifest, "events": events}
    for key, default, name in (("theme_file", "theme.json", "theme"), ("bindings_file", "bindings.json", "bindings")):
        p = _sub(key, default)
        if not p.exists():
            raise ContentError(f"缺少 {p.name}")
        try:
            tree[name] = _read_data(p)
        except json.JSONDecodeError as exc:
            raise ContentError(f"{p.name} 不是合法 JSON：{exc}") from exc
    bpath = _sub("base_setting_file", "base_setting.md")
    if not bpath.exists():
        raise ContentError(f"缺少 {bpath.name}")
    tree["base_setting"] = bpath.read_text(encoding="utf-8-sig")
    return tree


def load_pack(root: Path, known_patterns: set[str] | None = None) -> Pack:
    """加载 + 校验；有 error 直接抛 ContentError（报错文本可读，含全部 error）。"""
    tree = load_tree(root)
    res = validate_tree(tree, known_patterns)
    if not res.ok:
        raise ContentError(f"包 {root.name} 校验失败：\n" + res.report())
    for w in res.warnings:
        logger.warning("包 %s：%s", root.name, w)
    return Pack(
        root=Path(root), manifest=tree["manifest"], theme=tree["theme"], events=tree["events"],
        bindings=tree["bindings"], base_setting=tree["base_setting"], validation=res,
    )


def discover_packs(packs_dir: Path, known_patterns: set[str] | None = None) -> tuple[dict[str, Pack], dict[str, str]]:
    """扫描 content/pack/dungeon/*：只认 manifest.format==dungeon_v2 的目录。

    返回 (成功加载的 {pack_id: Pack}, 失败的 {目录名: 错误文本})。单包失败隔离，不影响其他包。
    """
    packs: dict[str, Pack] = {}
    failures: dict[str, str] = {}
    packs_dir = Path(packs_dir)
    if not packs_dir.is_dir():
        return packs, failures
    for d in sorted(packs_dir.iterdir()):
        if not d.is_dir():
            continue
        mpath = d / "manifest.json"
        if not mpath.exists():
            continue  # 旧格式包（yaml manifest 等）：不是我们的，跳过
        try:
            head = json.loads(mpath.read_text(encoding="utf-8-sig"))
        except Exception as exc:  # noqa: BLE001
            failures[d.name] = f"manifest.json 读取失败：{exc}"
            continue
        if not isinstance(head, dict) or head.get("format") != C.PACK_FORMAT:
            continue
        try:
            pack = load_pack(d, known_patterns)
        except DungeonError as exc:
            failures[d.name] = exc.zh
            logger.error("地牢包 %s 拒绝加载：%s", d.name, exc.zh)
            continue
        if pack.id in packs:
            failures[d.name] = f"pack id {pack.id} 与 {packs[pack.id].root.name} 重复"
            continue
        packs[pack.id] = pack
        logger.info("地牢包已加载：%s（%d 事件）", pack.id, len(pack.events))
    return packs, failures
