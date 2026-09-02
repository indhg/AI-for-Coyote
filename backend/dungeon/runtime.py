# -*- coding: utf-8 -*-
"""地牢运行时（M4）：把 engine + narrative + executor 串成 HTTP 可调用的服务对象。

持有主题包索引 + 当前 run；start/advance 产出前端所需的地牢状态。
叙事用真实 LLM（无 API Key 时降级为作者 seed，离线可玩）；体感走 FeedbackExecutor（dry_run 默认）。
"""
from __future__ import annotations

import logging
from pathlib import Path

from .engine import DungeonEngine, RunError
from .executor import FeedbackExecutor
from .feedback import resolve_feedback
from .loader import load_packs
from .narrative import NarrativeWriter
from .save import load_run, save_run
from ..ui_en import hint_en

logger = logging.getLogger("ai-for-coyote.dungeon.runtime")

SAMPLE_DIR = Path(__file__).resolve().parents[1] / "story_pack" / "sample"


class DungeonRuntime:
    def __init__(self, cfg, llm, safety, project_root: Path):
        self.cfg = cfg
        self.llm = llm
        self.safety = safety
        self.project_root = Path(project_root)
        self.pack_root = self.project_root / "content" / "pack"
        self.save_dir = self.project_root / "data" / "saves"

        self.packs: dict = {}
        self.engine: DungeonEngine | None = None
        self.writer: NarrativeWriter | None = None
        self.executor: FeedbackExecutor | None = None
        self.run: dict | None = None
        self._reload()

    # ------------------------------------------------------------------ 加载
    def _scan_pack_dirs(self) -> list[Path]:
        # 地牢主题包独立放在 content/pack/dungeon/，不与 .md 角色 DLC（DLC1-4）混排
        dirs = []
        dungeon_root = self.pack_root / "dungeon"
        if dungeon_root.is_dir():
            for d in sorted(dungeon_root.iterdir()):
                if d.is_dir() and (d / "manifest.yaml").is_file():
                    dirs.append(d)
        if not dirs:
            dirs = [SAMPLE_DIR]  # 无正式主题包时用内置 sample，保证网页有内容可玩
        return dirs

    def _reload(self) -> None:
        try:
            self.packs = load_packs(self._scan_pack_dirs())
        except Exception:  # noqa: BLE001
            logger.exception("主题包加载失败")
            self.packs = {}
        if self.packs:
            self.engine = DungeonEngine(self.packs)
            # 分层注入（T030 #5）：L0 骨架卡 = base_setting §6 基调摘要；旧 dm 拼接只作兜底
            base_setting = self._read_base_setting()
            base_summary = self._extract_base_summary(base_setting)
            dm = "\n\n".join([base_setting, self.engine.dm_prompt]).strip() if base_setting else self.engine.dm_prompt
            # 局内叙事：默认走作者 seed（即时、稳）；仅当 dungeon.ai_narrative=true 且配了 API Key 才调 LLM
            ai_narrative = bool(self.cfg.get("dungeon", {}).get("ai_narrative", False))
            llm = self.llm if (ai_narrative and (self.cfg["llm"].get("api_key") or "").strip()) else None
            self.writer = NarrativeWriter(llm=llm, base_summary=base_summary, dm_prompt=dm)
            self.executor = FeedbackExecutor(
                self.safety, dry_run=bool(self.cfg["app"].get("dry_run", True))
            )
        else:
            self.engine = self.writer = self.executor = None

    @staticmethod
    def _extract_base_summary(base_setting: str) -> str:
        """提取 base_setting 的「叙事者基调摘要」节作为 L0 骨架卡（找不到则取全文前 400 字）。"""
        if not base_setting:
            return ""
        for marker in ("## 6. 叙事者基调摘要", "## 5. 叙事者基调摘要", "叙事者基调摘要"):
            idx = base_setting.find(marker)
            if idx >= 0:
                return base_setting[idx:].strip()
        return base_setting[:400]

    def _read_base_setting(self) -> str:
        # 优先读「地牢大包」（content/pack/dungeon/00-地牢/）根下的 base_setting.md；回退旧路径
        for pack in self.packs.values():
            p = pack.pack_dir / "base_setting.md"
            if p.is_file():
                try:
                    return p.read_text(encoding="utf-8").strip()
                except Exception:  # noqa: BLE001
                    logger.exception("读取统一地牢设定失败")
                    return ""
        try:
            p = Path(__file__).resolve().parent / "base_setting.md"
            if p.is_file():
                return p.read_text(encoding="utf-8").strip()
        except Exception:  # noqa: BLE001
            logger.exception("读取统一地牢设定失败")
        return ""

    # ------------------------------------------------------------------ 查询
    def list_packs(self) -> list[dict]:
        out, seen = [], set()
        for tid, pack in self.packs.items():
            if tid in seen:
                continue
            seen.add(tid)
            out.append({
                "id": tid,
                "title": str(pack.manifest.get("title", tid)),
                "themes": [t.get("id") for t in pack.manifest.get("themes", [])],
                "event_count": len(pack.events),
            })
        return out

    def has_run(self) -> bool:
        return self.run is not None

    def _en(self) -> bool:
        """当前 UI 语言是否为英文（character.lang 运行时配置）。"""
        return str((self.cfg.get("character") or {}).get("lang") or "zh") == "en"

    def to_state(self) -> dict:
        if self.run is None:
            return {"active": False, "packs": self.list_packs()}
        return {"active": True, "packs": self.list_packs(), "run": self._snapshot()}

    # ------------------------------------------------------------------ 局内
    def _snapshot(self) -> dict:
        snap = self.engine.snapshot(self.run)
        snap.pop("rng_state", None)
        snap.pop("created_at", None)
        snap.pop("updated_at", None)
        return snap

    async def start(self, *, active_themes=None, mix_policy="mixed_pool", floors=3, seed=None, map_mode=False) -> dict:
        self._ensure_engine()
        themes = list(active_themes) if active_themes else list(self.engine.theme_ids)
        if map_mode:
            self.run = self.engine.start_map(
                active_themes=themes, mix_policy=mix_policy, floors=floors, seed=seed,
            )
        else:
            self.run = self.engine.start(
                preset_id="dungeon", active_themes=themes,
                mix_policy=mix_policy, floors=floors, seed=seed,
            )
        return await self._render(None)

    async def advance(self, *, choice_id=None, text=None, map_target=None) -> dict:
        self._ensure_run()
        # 急停闸（T030 #3）：急停中拒绝推进事件，解除后停在原事件
        if getattr(self.safety, "estop_active", False):
            raise RunError("急停中：先解除急停再继续（本事件已停住，不会丢进度）")
        if self.executor is not None:
            self.executor.en = self._en()
        if self.run.get("phase") == "map_select":
            if map_target:
                self.engine.map_select(
                    self.run, row=int(map_target["row"]), col=int(map_target["col"]),
                )
            else:
                # 纯文本模式：无 map_target 时自动选路（PRNG 随机选可达节点）
                self.engine.auto_select_next(self.run)
            return await self._render(text)
        prev = self.engine.current_event(self.run)
        prev_fb = resolve_feedback(prev, self.engine.bindings)
        self.engine.advance(self.run, choice_id=choice_id, intent_text=text)
        await self.executor.cleanup(prev_fb["on_exit"])  # 离开旧事件：清理
        return await self._render(text)

    async def _render(self, player_input) -> dict:
        # 地图选路开局：无当前事件，只返回地图状态
        if self.run.get("phase") == "map_select" and not self.run.get("event_id"):
            mv = self._map_view()
            return {"run": self._snapshot(), "event": None, "narrative": None, "map": mv}
        en = self._en()
        if self.executor is not None:
            self.executor.en = en
        ev = self.engine.current_event(self.run)
        fb = resolve_feedback(ev, self.engine.bindings)
        exec_res = await self.executor.execute(fb["on_enter"])  # 进入新事件：反馈
        narr = await self.writer.narrate(
            ev,
            player_input=player_input,
            player_nick=str(self.cfg["character"].get("player_nick") or "小柳"),
            theme_label=self._theme_label(ev.get("theme_id")),
            theme_tone=self._theme_tone(ev.get("theme_id")),
            run_memory=self.run.get("choice_log") or [],
            visit_n=self.run.get("visited", []).count(ev.get("id")),
            mark_flaring=bool(self.run.get("flags", {}).get("mark_flaring")),
            heat=int(self.run.get("run_state", {}).get("heat", 0)),
        )
        out = {
            "run": self._snapshot(),
            "event": self._event_view(ev),
            "narrative": narr,
            "feedback": {"hint": hint_en(fb["hint"]) if en else fb["hint"]},
            "executed": [e["label"] for e in exec_res["executed"]],
            "dropped": [d["reason"] for d in exec_res["dropped"]],
        }
        mv = self._map_view()
        if mv is not None:
            out["map"] = mv
        return out

    def _map_view(self) -> dict | None:
        """地图模式状态（节点/边/当前/可达），供前端路线图渲染。"""
        if not self.run.get("map_mode"):
            return None
        m = self.run.get("map") or {}
        return {
            "floor": m.get("floor"),
            "rows": m.get("rows"),
            "cols": m.get("cols"),
            "node_types": m.get("node_types"),
            "node_elite": m.get("node_elite"),
            "boss": m.get("boss"),
            "edges": m.get("edges"),
            "entry": m.get("entry"),
            "visited_nodes": m.get("visited_nodes") or [],
            "chains": m.get("chains") or {},
            "current": self.run.get("map_pos"),
            "reachable": (
                self.engine.map_candidates(self.run) if self.run.get("phase") == "map_select" else []
            ),
            "phase": self.run.get("phase"),
        }

    def _event_view(self, ev: dict) -> dict:
        return {
            "id": ev["id"],
            "title": ev.get("title", ""),
            "theme_id": ev.get("theme_id", ""),
            "kind": ev.get("kind", ""),
            "content_level": ev.get("content_level", ""),
            "tier": ev.get("tier", 1),
            "choices": [{"id": c.get("id"), "label": c.get("label")} for c in ev.get("choices") or []],
            "free_input": bool(ev.get("intents") or ev.get("reachable_event_ids")),
        }

    def _theme_label(self, theme_id: str) -> str:
        pack = self.packs.get(theme_id)
        if pack:
            for t in pack.manifest.get("themes", []):
                if t.get("id") == theme_id:
                    return str(t.get("label") or theme_id)
        return theme_id

    def _theme_tone(self, theme_id: str) -> str:
        """当前主题口吻（theme.yaml 的 tone，T030 #5：tone 字段此前从未被读取）。"""
        pack = self.packs.get(theme_id)
        if pack:
            tone = (pack.theme or {}).get("tone")
            if tone:
                return str(tone)
        return ""

    # ------------------------------------------------------------------ 存档
    def save(self, slot: str = "autosave") -> str:
        self._ensure_run()
        return save_run(self.engine, self.run, self.save_dir, slot=slot)

    async def load(self, slot: str = "autosave") -> dict:
        self._ensure_engine()
        preset = self.run.get("preset_id", "dungeon") if self.run else "dungeon"
        self.run = load_run(self.save_dir, preset, slot=slot)
        return await self._render(None)

    def restart(self) -> None:
        self.run = None

    # ------------------------------------------------------------------ 内部
    def _ensure_engine(self) -> None:
        if self.engine is None:
            raise RunError("没有可用的主题包（请先导入 DLC 主题包）")

    def _ensure_run(self) -> None:
        if self.run is None:
            raise RunError("当前没有进行中的地牢局（请先开始）")
