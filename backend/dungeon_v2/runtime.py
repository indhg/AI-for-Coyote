# -*- coding: utf-8 -*-
"""DungeonRuntime：对接 main.py 现有路由（签名与旧壳一致，路由不改）。

    self.dungeon = DungeonRuntime(cfg, self.llm, self.safety, PROJECT_ROOT)
    self.dungeon.executor.send = self.backend.apply
    GET  /api/dungeon/state    → to_state()
    GET  /api/dungeon/render   → render()（D11 E1：上一帧 render 只读，刷新恢复用）
    POST /api/dungeon/start    → await start(active_themes, mix_policy, floors, seed, map_mode)
    POST /api/dungeon/advance  → await advance(choice_id, text, map_target)
    POST /api/dungeon/move     → await move(node_id)   # map 选路（D25）
    POST /api/dungeon/save     → save(slot) -> path
    POST /api/dungeon/load     → await load(slot)
    POST /api/dungeon/restart  → restart()
    内容包安装后             → _reload()

mix_policy / floors / map_mode 是旧壳参数：新引擎单主题包、空间链固定，接受但忽略（记日志）。
llm：首批叙事恒用作者 seed（cfg.dungeon.ai_narrative 不接），保留参数不使用。
"""
from __future__ import annotations

import logging
from pathlib import Path

from . import constants as C
from .engine import Engine, Outcome, Run
from .errors import DungeonError
from .feedback import FeedbackExecutor
from .loader import Pack, discover_packs, known_patterns_default
from .render import build
from .rng import seed_from_any
from .save import read_save, save_path, write_save

logger = logging.getLogger("ai-for-coyote.dungeon_v2")


class DungeonRuntime:
    def __init__(self, cfg, llm, safety, project_root) -> None:
        self.cfg = cfg
        self.llm = llm
        self.safety = safety
        self.root = Path(project_root)
        self.executor = FeedbackExecutor(cfg, safety)
        self.packs: dict[str, Pack] = {}
        self.pack_errors: dict[str, str] = {}
        self.engine: Engine | None = None
        self.run: Run | None = None
        self.last_result: dict | None = None
        self._reload()

    # ---------- 包 ----------
    def packs_dir(self) -> Path:
        return self.root / "content" / "pack" / "dungeon"

    def _reload(self) -> None:
        try:
            self.packs, self.pack_errors = discover_packs(self.packs_dir(), known_patterns_default())
        except Exception as exc:  # noqa: BLE001
            logger.exception("地牢包扫描失败")
            self.packs, self.pack_errors = {}, {"*": str(exc)}
        # 正在进行的局所属包若被重载，引擎换新包对象（事件 id 不变即可继续）
        if self.run is not None and self.run.pack_id in self.packs:
            self.engine = Engine(self.packs[self.run.pack_id])

    def _pick_pack(self, active_themes) -> Pack:
        if not self.packs:
            detail = "；".join(f"{k}: {v.splitlines()[0]}" for k, v in self.pack_errors.items()) or "content/pack/dungeon 下没有 dungeon_v2 包"
            raise DungeonError("no_pack", f"没有可用的地牢主题包（{detail}）", "no dungeon pack available")
        wanted = [str(t) for t in (active_themes or []) if t]
        if not wanted:
            return next(iter(self.packs.values()))
        for pid, pack in self.packs.items():
            if pid in wanted or any(t in wanted for t in pack.themes):
                return pack
        raise DungeonError("pack_not_found", f"未找到主题 {wanted}", f"themes {wanted} not found")

    # ---------- 状态 ----------
    def _en(self) -> bool:
        try:
            return str(self.cfg["character"].get("lang") or "zh") == "en"
        except Exception:  # noqa: BLE001
            return False

    def to_state(self) -> dict:
        return {
            "active": self.run is not None and self.run.phase == "playing",
            "packs": [p.summary() for p in self.packs.values()],
            "run": self.run.snapshot(en=self._en()) if self.run else None,
            "engine": C.PACK_FORMAT,
            "pack_errors": dict(self.pack_errors),
            "estop": bool(getattr(self.safety, "estop_active", False)),
            "last_event": (self.last_result or {}).get("event"),
        }

    def render(self) -> dict:
        """上一帧 render（start/advance/load 的返回原样；D11 E1）。无局 → [no_run]。只读，不执行设备动作。"""
        if self.run is None or self.last_result is None:
            raise DungeonError("no_run", "没有进行中的地牢局，请先开始", "no active run")
        return self.last_result

    # ---------- 设备执行 ----------
    async def _run_feedback(self, outcome: Outcome | None) -> tuple[list, list, list[str]]:
        """按 Outcome 顺序执行设备动作：先【清理】（败北/结局），再新事件 feedback。"""
        assert self.run is not None and self.engine is not None
        executed: list = []
        dropped: list = []
        cores: list[str] = []
        if outcome is not None and outcome.cleanup:
            ex, dr = await self.executor.cleanup()
            executed += ex
            dropped += dr
            cores.append("清理")
        if outcome is None or outcome.entered:
            event = self.engine.current_event(self.run)
            plan_cores, actions = self.executor.plan(self.engine.pack.bindings, event, list(self.run.pending_feedback))
            ex, dr = await self.executor.run(actions)
            executed += ex
            dropped += dr
            cores += plan_cores
            self.run.pending_feedback = []
        return executed, dropped, cores

    def _render(self, executed, dropped, cores, outcome: Outcome | None) -> dict:
        assert self.run is not None and self.engine is not None
        result = build(self.engine.pack, self.engine, self.run, executed=executed, dropped=dropped,
                       cores=cores, en=self._en(), outcome=outcome)
        self.last_result = result
        return result

    # ---------- HTTP 动作 ----------
    async def start(self, active_themes=None, mix_policy: str = "mixed_pool", floors: int = 3,
                    seed=None, map_mode: bool = False, debug_state: dict | None = None) -> dict:
        pack = self._pick_pack(active_themes)
        if mix_policy not in ("", None, "mixed_pool") or int(floors or 3) != 3:
            logger.info("dungeon_v2 忽略旧壳参数 mix_policy=%r floors=%r", mix_policy, floors)
        master = seed_from_any(seed)
        self.engine = Engine(pack)
        # 进入 map：包 manifest.mode=map；或 start(map_mode=True) 且包为 map 包
        want_map = bool(map_mode) or getattr(pack, "mode", "chain") == "map"
        if bool(map_mode) and getattr(pack, "mode", "chain") != "map":
            logger.info("map_mode=True 但包 %s 非 map 包，忽略", pack.id)
            want_map = False
        self.run = self.engine.new_run(master, debug_state=debug_state, map_mode=want_map)
        logger.info("地牢开局：pack=%s seed=%d mode=%s str/dex/int=%d/%d/%d", pack.id, master, self.run.mode,
                    self.run.state.str, self.run.state.dex, self.run.state.int)
        executed, dropped, cores = await self._run_feedback(None)
        return self._render(executed, dropped, cores, None)

    async def advance(self, choice_id=None, text=None, map_target=None) -> dict:
        if self.run is None or self.engine is None:
            raise DungeonError("no_run", "没有进行中的地牢局，请先开始", "no active run")
        if bool(getattr(self.safety, "estop_active", False)):
            raise DungeonError("estop", "急停中，拒绝推进地牢", "E-Stop is on, dungeon advance refused")
        if choice_id is None and text:
            raise DungeonError("free_input_disabled", "本事件不接受自由输入，请点选项", "free input is disabled; pick a choice")
        if map_target is not None:
            logger.info("dungeon_v2 忽略 map_target=%r（请改用 POST /api/dungeon/move）", map_target)
        outcome = self.engine.advance(self.run, choice_id)
        executed, dropped, cores = await self._run_feedback(outcome)
        return self._render(executed, dropped, cores, outcome)

    async def move(self, node_id=None) -> dict:
        """map 选路：body {node_id}。"""
        if self.run is None or self.engine is None:
            raise DungeonError("no_run", "没有进行中的地牢局，请先开始", "no active run")
        if bool(getattr(self.safety, "estop_active", False)):
            raise DungeonError("estop", "急停中，拒绝选路", "E-Stop is on, dungeon move refused")
        if node_id is None or str(node_id).strip() == "":
            raise DungeonError("bad_node", "缺少 node_id", "missing node_id")
        outcome = self.engine.move(self.run, node_id)
        executed, dropped, cores = await self._run_feedback(outcome)
        return self._render(executed, dropped, cores, outcome)

    def save(self, slot: str = "autosave") -> str:
        if self.run is None:
            raise DungeonError("no_run", "没有进行中的地牢局，无法存档", "no active run to save")
        payload = {
            "pack_id": self.run.pack_id,
            "seed": self.run.seed,
            "rng_state": self.run.rng.get_state(),
            "run": self.run.to_dict(with_rng=False),
        }
        return write_save(save_path(self.root, slot), payload)

    async def load(self, slot: str = "autosave") -> dict:
        doc = read_save(save_path(self.root, slot))
        pack = self.packs.get(str(doc["pack_id"]))
        if pack is None:
            raise DungeonError("pack_not_found", f"存档所属主题包 {doc['pack_id']} 未加载", f"pack {doc['pack_id']} not loaded")
        run = Run.from_dict(doc["run"], doc["rng_state"])
        run.seed = int(doc["seed"])
        pack.event(run.event_id)  # 事件必须仍存在
        self.engine = Engine(pack)
        self.run = run
        # 读档不重放设备动作（安全：只在玩家推进时输出体感）
        return self._render([], [], [], None)

    def restart(self) -> None:
        """清掉当前局（E014「留」= 再来一局，走这里再 start）。设备清理由安全层/急停负责，这里不发命令。"""
        self.run = None
        self.engine = None
        self.last_result = None
