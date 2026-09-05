# -*- coding: utf-8 -*-
"""引擎：结算顺序（D2 §4.5，写死）。纯同步、无设备 IO；设备动作由 runtime 按 Outcome 执行。

advance(choice)：
  1. 状态/数值门槛（require 非属性键）→ 不满足：DungeonError(require_unmet)，状态不变
  2. 属性检定（require 属性键）→ run RNG 掷装备骰（ed6 再独立判 15% 归零）→ 记 run.log
       成功 → 本 choice；失败 → fail 分支（fail:{choice:n} 折叠，不二次检定）
  3. effects 逐条按序 → 全量钳制
  4. hp == 0（本次结算致 0：结算前 hp>0，或本次有 hp 负 delta）→ 【清理】→ 败北回安全区，覆盖 next
  5. 否则若 choice.gate_check → crossed_gate = (mark_stage >= form and ma >= 100)
       crossed → next；未 crossed → next_uncrossed
  6. next == end → 【清理】先于结局锁定；否则进入 next
结局：escape/stay → phase=ended（可 restart/新开）；sink → phase=locked（本局不再给探索选项）。
急停由 runtime 在调用 advance 前拦截（safety.estop_active）。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import constants as C
from .checks import resolve_check, split_require, unmet_gates, unmet_gates_struct
from .effects import apply_effects
from .errors import DungeonError
from .loader import Pack
from .narrative import select_variant
from .rng import RunRNG
from .schema import parse_feedback
from .state import RunState
from .map_gen import generate_map
from .map_logic import apply_move, mark_ending_reached, node_by_id


@dataclass
class Run:
    pack_id: str
    seed: int
    rng: RunRNG
    state: RunState
    event_id: str = ""
    visit_n: int = 0
    visits: dict = field(default_factory=dict)
    turn: int = 0
    phase: str = "playing"           # playing / ended / locked
    ending: str | None = None        # escape / stay / sink
    defeats: int = 0
    log: list = field(default_factory=list)
    variant: dict = field(default_factory=dict)
    last_exit: str | None = None
    pending_feedback: list = field(default_factory=list)   # 本事件待执行的核心词（runtime 消费）
    flags_seen: dict = field(default_factory=dict)
    mode: str = "chain"            # chain | map（D25）
    map: dict | None = None        # map 路网运行态；chain 恒 None

    # ---------- 序列化 ----------
    def to_dict(self, with_rng: bool = True) -> dict:
        d = {
            "pack_id": self.pack_id, "seed": self.seed, "event_id": self.event_id,
            "visit_n": self.visit_n, "visits": dict(self.visits), "turn": self.turn,
            "phase": self.phase, "ending": self.ending, "defeats": self.defeats,
            "log": list(self.log), "variant": dict(self.variant), "last_exit": self.last_exit,
            "pending_feedback": list(self.pending_feedback), "state": self.state.to_dict(),
            "mode": self.mode, "map": self.map,
        }
        if with_rng:
            d["rng_state"] = self.rng.get_state()
        return d

    @classmethod
    def from_dict(cls, d: dict, rng_state) -> "Run":
        run = cls(
            pack_id=str(d["pack_id"]), seed=int(d["seed"]), rng=RunRNG.from_state(rng_state),
            state=RunState.from_dict(d.get("state") or {}),
        )
        run.event_id = str(d.get("event_id", ""))
        run.visit_n = int(d.get("visit_n", 0))
        run.visits = {str(k): int(v) for k, v in (d.get("visits") or {}).items()}
        run.turn = int(d.get("turn", 0))
        run.phase = str(d.get("phase", "playing"))
        run.ending = d.get("ending")
        run.defeats = int(d.get("defeats", 0))
        run.log = list(d.get("log") or [])
        run.variant = dict(d.get("variant") or {})
        run.last_exit = d.get("last_exit")
        run.pending_feedback = list(d.get("pending_feedback") or [])
        run.mode = str(d.get("mode") or "chain")
        run.map = d.get("map")
        return run

    def snapshot(self, en: bool = False) -> dict:
        """HUD/render 用 run 快照（§4.1 字段拍平 + 进度 + 日志尾）。不含 rng_state。en → 骰子名/描述英文。"""
        s = self.state.to_dict(en=en)
        s.update({
            "seed": self.seed, "pack_id": self.pack_id, "event_id": self.event_id,
            "visit_n": self.visit_n, "turn": self.turn, "phase": self.phase, "ending": self.ending,
            "defeats": self.defeats, "visits": dict(self.visits),
            "log": list(self.log[-20:]), "engine": C.PACK_FORMAT,
            "mode": self.mode,
        })
        return s


@dataclass
class Outcome:
    event_before: str
    choice_index: int                 # 玩家点的（1-based）
    choice_label: str
    effective_index: int              # 实际生效的（折叠后，1-based）
    settlement: str
    effective_label: str = ""         # 实际生效选项的 label（折叠后；自定义 fail 无选项时为空）D11 E4
    check: dict | None = None
    folded: bool = False
    effects: dict = field(default_factory=dict)
    defeat: bool = False
    gate_checked: bool = False
    crossed: bool = False
    ending: str | None = None
    next_event: str | None = None
    cleanup: bool = False             # 需要【清理设备】（败北 / 结局）
    entered: bool = False             # 是否进入了新事件（要执行新事件 feedback）
    exit_text: str = ""
    estop_overrides: bool = False


class Engine:
    def __init__(self, pack: Pack) -> None:
        self.pack = pack

    # ---------- 开局 ----------
    def new_run(self, seed: int, debug_state: dict | None = None, map_mode: bool | None = None) -> Run:
        # D25_MAP_MODE
        rng = RunRNG(seed)
        state = RunState.roll_new(rng)
        if debug_state:  # 仅测试用：覆盖开局数值（不经 HTTP 暴露）
            for k, v in debug_state.items():
                if hasattr(state, k):
                    setattr(state, k, v)
            state.clamp_all()
        run = Run(pack_id=self.pack.id, seed=int(seed), rng=rng, state=state)
        pack_is_map = getattr(self.pack, "mode", C.PACK_MODE_CHAIN) == C.PACK_MODE_MAP
        use_map = pack_is_map if map_mode is None else bool(map_mode)
        if use_map and not pack_is_map:
            # 链式包不能强行 map
            use_map = False
        run.mode = C.PACK_MODE_MAP if use_map else C.PACK_MODE_CHAIN
        self._log(run, {"type": "start", "seed": int(seed), "str": state.str, "dex": state.dex,
                        "int": state.int, "mode": run.mode})
        if use_map:
            room_events: dict[str, list[str]] = {}
            titles: dict[str, str] = {}
            for eid, ev in self.pack.events.items():
                titles[eid] = str(ev.get("title") or eid)
                if ev.get("kind") == "ending":
                    continue
                room_events.setdefault(str(ev.get("room")), []).append(eid)
            graph = generate_map(
                int(seed),
                room_events={k: tuple(v) for k, v in room_events.items()},
                event_titles=titles,
            )
            for nd in graph["nodes"]:
                nd["title"] = titles.get(nd["event_id"], nd.get("title"))
            run.map = graph
            entry = node_by_id(graph, graph["current"])
            self.enter(run, str(entry["event_id"]), prefix=None)
            run.map["awaiting_move"] = False
        else:
            self.enter(run, self.pack.start_event, prefix=None)
        return run

    # ---------- 进入事件 ----------
    def enter(self, run: Run, eid: str, prefix: str | None) -> dict:
        ev = self.pack.event(eid)
        run.visits[eid] = int(run.visits.get(eid, 0)) + 1
        run.visit_n = run.visits[eid]
        run.event_id = eid
        run.turn += 1
        run.variant = select_variant(run.seed, ev, run.visit_n)
        run.last_exit = prefix
        for k, v in (ev.get("flags") or {}).items():
            run.state.flags[str(k)] = str(v)
        run.pending_feedback = parse_feedback(ev.get("feedback", ""))
        self._log(run, {"type": "enter", "event": eid, "visit_n": run.visit_n,
                        "variant": run.variant["index"], "feedback": list(run.pending_feedback)})
        return ev

    def current_event(self, run: Run) -> dict:
        return self.pack.event(run.event_id)

    # ---------- choice 查找 / 门槛视图 ----------
    @staticmethod
    def choice_index(event: dict, choice_id) -> int:
        """choice_id 允许 int / '1' / 'c1'；返回 0-based 下标，非法抛 DungeonError。"""
        n = len(event.get("choices") or [])
        raw = str(choice_id if choice_id is not None else "").strip().lower()
        if raw.startswith("c"):
            raw = raw[1:]
        if not raw.isdigit() or not (1 <= int(raw) <= n):
            raise DungeonError("bad_choice", f"选项 {choice_id!r} 不存在（1..{n}）", f"choice {choice_id!r} out of range 1..{n}")
        return int(raw) - 1

    def choice_gate_view(self, run: Run, event: dict) -> list[dict]:
        """每条 choice 的门槛/检定视图（render 用）：disabled + reason + check 描述。"""
        views = []
        for ch in event.get("choices") or []:
            attr_check, gates = split_require(ch.get("require"))
            unmet = unmet_gates_struct(run.state, gates)
            views.append({
                "disabled": bool(unmet),
                "disabled_reason": "；".join(u["text"] for u in unmet) if unmet else None,
                "unmet": unmet or None,
                "check": {"attr": attr_check[0], "tn": attr_check[1], "attr_value": run.state.attr(attr_check[0]),
                          "dice": run.state.dice} if attr_check else None,
                "gates": gates or None,
            })
        return views

    # ---------- map 选路 ----------
    def move(self, run: Run, node_id) -> Outcome:
        """POST /api/dungeon/move：仅 map 模式、awaiting_move 且 reachable。"""
        if run.mode != C.PACK_MODE_MAP or not run.map:
            raise DungeonError("not_map", "当前不是 map 模式，无法选路", "not in map mode")
        if run.phase == "locked":
            raise DungeonError("run_locked", "本局已沉没，请重开新局", "run is locked")
        if run.phase == "ended":
            raise DungeonError("run_ended", "本局已结束，请重开新局", "run has ended")
        tgt = apply_move(run.map, str(node_id), run.state)
        prefix = f"你走向「{tgt.get('title') or tgt['id']}」。"
        self.enter(run, str(tgt["event_id"]), prefix=prefix)
        self._log(run, {"type": "move", "node": tgt["id"], "event": tgt["event_id"], "floor": tgt["floor"]})
        out = Outcome(event_before="", choice_index=0, choice_label="move",
                      effective_index=0, settlement="move")
        out.entered = True
        out.next_event = run.event_id
        out.exit_text = prefix
        return out

    # ---------- 推进 ----------
    def advance(self, run: Run, choice_id) -> Outcome:
        if run.phase == "locked":
            raise DungeonError("run_locked", "本局已沉没，不再给探索选项；请重开新局", "run is locked (sink ending); start a new run")
        if run.phase == "ended":
            raise DungeonError("run_ended", "本局已结束，请重开新局", "run has ended; start a new run")
        if run.mode == C.PACK_MODE_MAP and run.map and run.map.get("awaiting_move"):
            raise DungeonError("not_awaiting", "当前在选路阶段，请先 POST /api/dungeon/move", "awaiting move; call move first")
        ev = self.current_event(run)
        idx = self.choice_index(ev, choice_id)
        choice = ev["choices"][idx]
        attr_check, gates = split_require(choice.get("require"))

        # 1. 状态/数值门槛 → 后端拒绝
        unmet = unmet_gates(run.state, gates)
        if unmet:
            raise DungeonError("require_unmet", "选项不可用：" + "；".join(unmet), "choice locked: " + "; ".join(unmet))

        out = Outcome(event_before=run.event_id, choice_index=idx + 1, choice_label=str(choice["label"]),
                      effective_index=idx + 1, settlement=str(choice["settlement"]))
        out.effective_label = out.choice_label
        eff_choice = choice
        custom_fail = None

        # 2. 属性检定
        if attr_check is not None:
            attr, tn = attr_check
            rec = resolve_check(run.state, run.rng, attr, tn)
            out.check = rec
            if not rec["success"]:
                fail = choice.get("fail") or {}
                out.folded = True
                if "choice" in fail:
                    out.effective_index = int(fail["choice"])
                    eff_choice = ev["choices"][out.effective_index - 1]
                    out.effective_label = str(eff_choice.get("label", ""))
                else:
                    custom_fail = fail  # {next, settlement, exit}：无 effects
                    eff_choice = None
                    out.effective_label = ""

        if eff_choice is not None:
            out.settlement = str(eff_choice["settlement"])
            out.exit_text = str(eff_choice.get("exit", ""))
            out.estop_overrides = bool(eff_choice.get("estop_overrides"))
            effects = eff_choice.get("effects")
            next_id = str(eff_choice["next"])
        else:
            out.settlement = str(custom_fail.get("settlement", out.settlement))
            out.exit_text = str(custom_fail.get("exit", ""))
            effects = None
            next_id = str(custom_fail["next"])

        # 3. effects → 钳制
        hp_before = run.state.hp
        summary = apply_effects(run.state, effects, run.visit_n, run.rng)
        run.state.clamp_all()
        out.effects = summary
        hp_hit = any(a["key"] == "hp" and a["value"] < 0 for a in summary["applied"])

        entry = {"type": "advance", "event": run.event_id, "visit_n": run.visit_n,
                 "choice": out.choice_index, "label": out.choice_label, "check": out.check,
                 "folded_to": out.effective_index if out.folded else None,
                 "folded_label": out.effective_label if out.folded else None,
                 "settlement": out.settlement,
                 "effects": [{"key": a["key"], "value": a["value"], "after": a["after"]} for a in summary["applied"]],
                 "skipped": summary["skipped"], "dice_gain": summary["dice_gain"]}

        # 4. 败北
        if run.state.hp == 0 and (hp_before > 0 or hp_hit):
            out.defeat = True
            out.cleanup = True
            run.defeats += 1
            entry["defeat"] = True
            self._log(run, entry)
            defeat_line = str(self.pack.theme.get("defeat_line") or "力气到了底。你是怎么回到这里的，记不清了。")
            if run.mode == C.PACK_MODE_MAP and run.map is not None:
                # 裁决 21：map 败北 = 本局结束（无回流/无轮回）
                run.phase = "ended"
                run.ending = None
                run.last_exit = defeat_line
                run.pending_feedback = []
                run.map["awaiting_move"] = False
                out.entered = False
                out.next_event = None
                out.exit_text = defeat_line
                entry["map_defeat_end"] = True
                return out
            self.enter(run, self.pack.safe_room, prefix=defeat_line)
            out.entered = True
            out.next_event = run.event_id
            return out

        # 5. crossed_gate（只在 gate_check 选项结算后）
        if eff_choice is not None and eff_choice.get("gate_check"):
            out.gate_checked = True
            crossed = run.state.stage_at_least(C.GATE_STAGE_MIN) and run.state.ma >= C.MO_HUA_BUFFER
            entry["gate_check"] = {"stage": run.state.mark_stage, "ma": run.state.ma, "crossed": crossed}
            if crossed:
                run.state.crossed_gate = True
                out.crossed = True
            else:
                next_id = str(eff_choice["next_uncrossed"])

        # 6. next / ending / map return
        if next_id == C.END_TOKEN:
            ending = C.ENDING_BY_SETTLEMENT.get(out.settlement, "escape")
            out.ending = ending
            out.cleanup = True                     # 清理先于锁定（runtime 先执行 cleanup 再返回）
            run.ending = ending
            run.phase = "locked" if ending == "sink" else "ended"
            run.pending_feedback = []
            entry["ending"] = ending
            if run.mode == C.PACK_MODE_MAP and run.map is not None:
                mark_ending_reached(run.map, ending)
                run.map["awaiting_move"] = False
            self._log(run, entry)
            return out

        if next_id == C.MAP_RETURN:
            if run.mode != C.PACK_MODE_MAP or run.map is None:
                raise DungeonError("content", "next=map 但当前不是 map 模式")
            entry["map_return"] = True
            self._log(run, entry)
            run.map["awaiting_move"] = True
            out.entered = False
            out.next_event = None
            return out

        self._log(run, entry)
        self.enter(run, next_id, prefix=out.exit_text or None)
        out.entered = True
        out.next_event = run.event_id
        # map：进入结局事件后仍非 awaiting_move
        if run.mode == C.PACK_MODE_MAP and run.map is not None:
            run.map["awaiting_move"] = False
        return out

    # ---------- 日志 ----------
    @staticmethod
    def _log(run: Run, entry: dict) -> None:
        entry = {"turn": run.turn, **entry}
        run.log.append(entry)
        if len(run.log) > C.LOG_MAX:
            del run.log[: len(run.log) - C.LOG_MAX]
