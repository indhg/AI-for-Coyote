# -*- coding: utf-8 -*-
"""地牢引擎（M2）：run 状态、事件环、楼层/房间、随机事件池、结局判定。

设计（对齐 M1 结论 §6）：
- 事件图是作者写死的（choices 的 next_event_id 是作者边），引擎只「推进」不「编图」。
- mix_policy（single_theme/per_floor/per_room/mixed_pool）+ seed 只作用于「入口选择」与
  「自由移动（reachable_event_ids）」两处随机，作者边不受随机影响。
- 随机用 run 内置 RNG 状态（getstate/setstate），同 seed 同路径 = 同结果（可复现，存档可续）。
"""
from __future__ import annotations

import random
import time
import uuid
from typing import Optional

from .loader import ThemePack

# 初始状态（dry_run 起手值，正式数值由地牢预设决定）
HP_START = 8
WILL_START = 6
MAX_HP = 10
MAX_WILL = 10

# 淫纹机制（底座设定 §4，所有主题共享）
HEAT_MAX = 100
HEAT_FLARE_AT = 80        # 默认发作阈值（按层覆盖）
HEAT_FLARE_BY_FLOOR = {1: 80, 2: 65, 3: 50}   # 越深越容易发作（T028 定稿）
HEAT_HYSTERESIS = 10      # 滞回：发作中 heat 跌破（阈值-10）才熄，防边界反复
HEAT_COOL_VALUE = 30      # 喂饱后回落值
HEAT_SAFE_ROOM_COOL = 20  # 安全室每停留 1 事件降温（带防刷：上一事件是 safe 则不重复减）
KINDLE_ORGASM_AT = 2      # 高潮计数达到即自动点燃

# 地图模式（杀戮尖塔式分层 DAG，T028 定稿）
MAP_COLS = 4                      # 列固定 4（分支密度/UI 稳定）
MAP_ROWS_BY_FLOOR = {1: 4, 2: 5, 3: 4}   # 行随深度；终层末行之后是独立 Boss 行
MAP_EDGE_SPAN = 2                 # 扇形跨度：目标列 ∈ [c-span, c+span]
MAP_EXTRA_EDGES = (1, 2)          # 每个节点额外叠加 1~2 条边（分支/交叉）
MAP_NODE_WEIGHTS = {"encounter": 45, "treasure": 15, "safe": 15, "corridor": 25}
MAP_CHAIN_MAX = 6                 # 单节点内事件链上限（防作者环/死循环，超限强制回图）

MIX_POLICIES = {"single_theme", "per_floor", "per_room", "mixed_pool"}

ROOM_TYPES_CYCLE = ["corridor", "encounter", "safe"]


class RunError(Exception):
    """地牢推进错误（非法选择 / 未知事件 / 无路可走）。"""


def _fresh_rng_state(seed: int):
    r = random.Random(seed)
    return r.getstate()


def new_run(
    *,
    preset_id: str = "dungeon",
    active_themes: list[str] | None = None,
    mix_policy: str = "single_theme",
    floors: int = 3,
    seed: int | None = None,
) -> dict:
    """新建一个 run（尚未进入事件）。"""
    if mix_policy not in MIX_POLICIES:
        raise RunError(f"非法 mix_policy：{mix_policy!r}")
    seed = int(seed) if seed is not None else int(time.time_ns() % (2 ** 31))
    return {
        "preset_id": preset_id,
        "active_themes": list(active_themes or []),
        "mix_policy": mix_policy,
        "seed": seed,
        "floors": max(1, int(floors)),
        "floor_index": 1,
        "room_index": 1,
        "map_mode": False,       # False=旧线性作者边；True=地图模式（路线图选路）
        "map_pos": None,         # 地图模式位置 {floor,row,col}（floor_index/room_index 由它派生）
        "event_id": None,
        "turn_index": 0,
        "run_state": {"hp": HP_START, "will": WILL_START, "affinity": {}, "heat": 0, "orgasm_count": 0},
        "flags": {},
        "visited": [],
        "choice_log": [],
        "phase": "run",          # run | ending
        "ending_id": None,
        "rng_state": _fresh_rng_state(seed),
        "created_at": int(time.time()),
        "updated_at": int(time.time()),
    }


def _rng_draw(run: dict, seq: list, weights=None):
    """用 run 内置 RNG 抽一次，并写回状态（可复现、可存档）。"""
    r = random.Random()
    r.setstate(run["rng_state"])
    if weights is not None:
        idx = r.choices(range(len(seq)), weights=weights, k=1)[0]
        result = seq[idx]
    else:
        result = r.choice(seq)
    run["rng_state"] = r.getstate()
    return result


class DungeonEngine:
    """合并多个主题包，提供地牢 run 的推进。"""

    def __init__(self, packs: dict[str, ThemePack]):
        if not packs:
            raise RunError("至少需要一个主题包")
        self.packs = packs
        self.events: dict[str, dict] = {}
        self.bindings: dict[str, dict] = {}
        self.theme_ids: list[str] = []
        seen_pack_ids: set[int] = set()
        for pack in packs.values():
            if id(pack) in seen_pack_ids:
                continue  # 同一实例重复注册（测试/单包多主题），只注册一次
            seen_pack_ids.add(id(pack))
            # 跨包事件 id 冲突检查（不同实例后写覆盖是静默 bug 源）
            dup = sorted(set(pack.event_index) & set(self.events))
            if dup:
                raise RunError(f"主题包事件 id 冲突：{dup[:5]}（跨包撞名，拒绝加载）")
            self.events.update(pack.event_index)
            dup_b = sorted(set(pack.binding_index) & set(self.bindings))
            if dup_b:
                raise RunError(f"主题包绑定 id 冲突：{dup_b[:5]}（跨包撞名，拒绝加载）")
            self.bindings.update(pack.binding_index)
            for tid in pack.theme_ids:
                if tid not in self.theme_ids:
                    self.theme_ids.append(tid)
        self.entry_ids = [
            eid for eid, e in self.events.items()
            if e.get("trigger", {}).get("type") == "enter"
        ]
        self.dm_prompt = "\n\n".join(p.dm_prompt for p in packs.values() if p.dm_prompt)

    # ------------------------------------------------------------------ 工具
    def _active_themes(self, run: dict) -> list[str]:
        return [t for t in run["active_themes"] if t in self.theme_ids] or self.theme_ids

    def _theme_for_floor(self, run: dict, floor: int) -> str:
        themes = self._active_themes(run)
        return themes[(floor - 1) % len(themes)]

    def _theme_for_room(self, run: dict, room_index: int) -> str:
        themes = self._active_themes(run)
        return themes[(room_index - 1) % len(themes)]

    def _current_theme(self, run: dict) -> str:
        """按 mix_policy 决定「当前 beat」应归属的主题（仅自由移动/入口用）。"""
        themes = self._active_themes(run)
        if run["mix_policy"] == "per_floor":
            return self._theme_for_floor(run, run["floor_index"])
        if run["mix_policy"] == "per_room":
            return self._theme_for_room(run, run["room_index"])
        if run["mix_policy"] == "mixed_pool":
            return _rng_draw(run, themes)
        return themes[0]  # single_theme

    def _pool(self, run: dict, event_ids: list[str]) -> list[dict]:
        """把候选事件按 mix_policy/主题亲和过滤成可抽池（含权重）。"""
        active = set(self._active_themes(run))
        theme = self._current_theme(run) if run["mix_policy"] != "mixed_pool" else None
        items = []
        weights = []
        for eid in event_ids:
            e = self.events.get(eid)
            if not e:
                continue
            tid = e.get("theme_id", "")
            if run["mix_policy"] == "mixed_pool":
                if tid not in active:
                    continue
                w = self._mix_weight(tid)
            else:
                if theme and tid != theme:
                    continue
                if tid not in active:
                    continue
                w = self._mix_weight(tid)
            items.append(eid)
            weights.append(w)
        return items, weights

    def _mix_weight(self, theme_id: str) -> float:
        pack = self.packs.get(theme_id)
        if not pack:
            return 1.0
        try:
            return float(pack.manifest.get("mix", {}).get("mix_weight", 1.0))
        except (TypeError, ValueError):
            return 1.0

    def _pick_event(self, run: dict, candidates: list[str]) -> str:
        items, weights = self._pool(run, candidates)
        if not items:
            raise RunError("当前没有可达事件（事件池为空）")
        if len(items) == 1:
            return items[0]
        return _rng_draw(run, items, weights=weights)

    # ------------------------------------------------------------------ start
    def start(
        self,
        *,
        preset_id: str = "dungeon",
        active_themes: list[str] | None = None,
        mix_policy: str = "single_theme",
        floors: int = 3,
        seed: int | None = None,
    ) -> dict:
        """新建并进入入口事件。"""
        run = new_run(
            preset_id=preset_id,
            active_themes=active_themes or list(self.theme_ids),
            mix_policy=mix_policy,
            floors=floors,
            seed=seed,
        )
        if not self.entry_ids:
            raise RunError("主题包缺少入口事件（trigger.type=enter）")
        entry = self._pick_event(run, self.entry_ids)
        self._enter(run, entry)
        return run

    def generate_floor_plan(self, run: dict, rooms_per_floor: int = 4) -> list[dict]:
        """按 seed 生成房间序列（含 Boss 房与结局房）。

        返回 [{floor, room, room_type, theme_id}]。房间类型在 corridor/encounter/safe 轮换；
        最后一层末尾追加 boss 房与结局房。主题分配依 mix_policy；用 run 内置 RNG（可复现）。
        该序列供「自由移动/随机装配」使用；作者图（choices）不依赖它。
        """
        themes = self._active_themes(run)
        plan = []
        idx = 0
        for f in range(1, run["floors"] + 1):
            for r in range(1, rooms_per_floor + 1):
                idx += 1
                room_type = ROOM_TYPES_CYCLE[(idx - 1) % len(ROOM_TYPES_CYCLE)]
                theme = self._floor_plan_theme(run, themes, f, r)
                plan.append({"floor": f, "room": r, "room_type": room_type, "theme_id": theme})
        last = run["floors"]
        plan.append({"floor": last, "room": rooms_per_floor + 1, "room_type": "boss",
                     "theme_id": self._floor_plan_theme(run, themes, last, rooms_per_floor + 1)})
        plan.append({"floor": last, "room": rooms_per_floor + 2, "room_type": "safe",
                     "theme_id": themes[0]})
        return plan

    def _floor_plan_theme(self, run: dict, themes: list[str], floor: int, room: int) -> str:
        if run["mix_policy"] == "per_floor":
            return themes[(floor - 1) % len(themes)]
        if run["mix_policy"] == "per_room":
            return themes[(room - 1) % len(themes)]
        if run["mix_policy"] == "mixed_pool":
            return _rng_draw(run, themes)
        return themes[0]  # single_theme

    # ------------------------------------------------------------------ 地图生成（杀戮尖塔式分层 DAG）
    def generate_floor_map(self, floor: int, *, seed: int | None = None) -> dict:
        """构造式生成一层杀戮尖塔式网状路线图（DAG）。

        规则（T028 定稿 + 用户确认）：
        - 列固定 MAP_COLS；行数随深度 MAP_ROWS_BY_FLOOR；末行精英，其后独立 Boss 行（单节点）
        - 入口连第 1 行 3 个节点（「看见三条路」）
        - elite 是**标记**不是房型：节点类型为 encounter + elite=True（装配时抽 high 强度事件）
        - 连边三遍：a) 下一行每节点先指派 1 父节点（最近列+随机，保证入边/必连通）
                    b) 上一行每节点叠加 1~2 条扇形额外边（跨度 ±MAP_EDGE_SPAN → 分支/交叉/合并）
                    c) 修补无出边节点；末行精英必连 Boss
        - 类型：普通行按权重 encounter/treasure/safe/corridor；每层强制 ≥1 safe；末行精英；Boss 行 boss
        - RNG：独立 Random(seed*1000+floor)，不消耗 run 推进 RNG → 同 seed 同图、读档可复现
        """
        rng = random.Random((int(seed or 0) * 1000) + int(floor))
        rows = MAP_ROWS_BY_FLOOR.get(int(floor), 5)
        cols = MAP_COLS
        boss = {"row": rows + 1, "col": rng.randrange(cols)}

        # 类型分配（elite 是标记，类型仍为 encounter）
        # row1 只放 3 个节点（= 入口 3 条，全部可达）；row2+ 每行 4 列
        type_keys = list(MAP_NODE_WEIGHTS)
        type_weights = [MAP_NODE_WEIGHTS[k] for k in type_keys]
        node_types: dict[str, str] = {}
        node_elite: dict[str, bool] = {}
        by_row: dict[int, list[dict]] = {}
        for r in range(1, rows + 1):
            by_row.setdefault(r, [])
            cols_this = 3 if r == 1 else cols  # row1 3 节点（入口全连，防孤立）
            for c in range(cols_this):
                by_row[r].append({"row": r, "col": c})
                elite = r == rows  # 末行 = 精英行
                node_types[f"{r},{c}"] = "encounter" if elite else rng.choices(type_keys, weights=type_weights, k=1)[0]
                node_elite[f"{r},{c}"] = elite
        by_row[rows + 1] = [boss]
        if not any(t == "safe" for t in node_types.values()):
            swap = rng.choice([k for k, t in node_types.items() if t in ("encounter", "corridor")])
            node_types[swap] = "safe"

        # 连边 a) 入口 → 第 1 行全部 3 个节点（「看见三条路」，row1 无孤立）
        edges: list[dict] = []
        entry_targets = sorted(by_row[1], key=lambda n: n["col"])
        for t in entry_targets:
            edges.append({"from": {"row": 0, "col": 0}, "to": {"row": t["row"], "col": t["col"]}})

        # 连边 b) 每节点先指派 1 父（保证入边）
        for r in range(2, rows + 2):
            prev = by_row[r - 1]
            for n in by_row.get(r, []):
                cands = [p for p in prev if abs(p["col"] - n["col"]) <= MAP_EDGE_SPAN] or prev
                parent = rng.choice(cands)
                edges.append({"from": {"row": parent["row"], "col": parent["col"]}, "to": {"row": n["row"], "col": n["col"]}})

        # 连边 c) 叠加分支/交叉边（网状）
        for r in range(1, rows + 1):
            for p in by_row.get(r, []):
                nxt = by_row.get(r + 1, [])
                if not nxt:
                    continue
                cands = [n for n in nxt if abs(n["col"] - p["col"]) <= MAP_EDGE_SPAN]
                if not cands:
                    continue
                for _ in range(rng.randint(*MAP_EXTRA_EDGES)):
                    t = rng.choice(cands)
                    e = {"from": {"row": p["row"], "col": p["col"]}, "to": {"row": t["row"], "col": t["col"]}}
                    if e not in edges:
                        edges.append(e)

        # 连边 d) 修补无出边节点；末行精英必连 Boss
        for r in range(1, rows + 1):
            for p in by_row.get(r, []):
                if not any(e["from"] == {"row": p["row"], "col": p["col"]} for e in edges):
                    nxt = by_row.get(r + 1, [boss])
                    t = min(nxt, key=lambda n: abs(n["col"] - p["col"]))
                    edges.append({"from": {"row": p["row"], "col": p["col"]}, "to": {"row": t["row"], "col": t["col"]}})
        for p in by_row.get(rows, []):
            if not any(e["from"] == {"row": p["row"], "col": p["col"]} and e["to"]["row"] == rows + 1 for e in edges):
                edges.append({"from": {"row": p["row"], "col": p["col"]}, "to": {"row": boss["row"], "col": boss["col"]}})

        return {
            "floor": int(floor),
            "rows": rows,
            "cols": cols,
            "node_types": dict(node_types),
            "node_elite": dict(node_elite),
            "boss": dict(boss),
            "edges": edges,
            "entry": [{"row": 1, "col": t["col"]} for t in entry_targets],
        }

    # ------------------------------------------------------------------ 地图模式推进（M5 接线）
    def start_map(
        self,
        *,
        active_themes: list[str] | None = None,
        mix_policy: str = "mixed_pool",
        floors: int = 3,
        seed: int | None = None,
    ) -> dict:
        """地图模式开局：生成第 1 层图，进入选路状态。"""
        run = new_run(
            preset_id="dungeon",
            active_themes=active_themes or list(self.theme_ids),
            mix_policy=mix_policy,
            floors=floors,
            seed=seed,
        )
        run["map_mode"] = True
        run["phase"] = "map_select"     # 地图选路阶段
        run["map_pos"] = None           # 入口前
        run["map"] = self._new_floor_state(run, 1)
        return run

    def _new_floor_state(self, run: dict, floor: int) -> dict:
        """生成一层地图并初始化状态（含装配记录/已访问节点）。"""
        m = self.generate_floor_map(floor, seed=run["seed"])
        return {
            "floor": floor,
            "rows": m["rows"],
            "cols": m["cols"],
            "node_types": m["node_types"],
            "node_elite": m["node_elite"],
            "boss": m["boss"],
            "edges": m["edges"],
            "entry": m["entry"],
            "chains": {},              # "r,c" -> 装配的事件链入口 id
            "visited_nodes": [],       # 已完成的节点 "r,c"
        }

    def _map_node_key(self, pos: dict) -> str:
        return f"{pos['row']},{pos['col']}"

    def map_candidates(self, run: dict) -> list[dict]:
        """当前可达节点（下一行）：从 map_pos 的出边；开局=entry。"""
        m = run.get("map") or {}
        edges = m.get("edges") or []
        if not run.get("map_pos"):
            return [dict(n) for n in m.get("entry") or []]
        cur = run["map_pos"]
        out = []
        for e in edges:
            if e["from"] == {"row": cur["row"], "col": cur["col"]}:
                node = {"row": e["to"]["row"], "col": e["to"]["col"]}
                if node not in out:
                    out.append(node)
        return out

    def map_select(self, run: dict, *, row: int, col: int) -> dict:
        """选择下一行节点 → 装配事件链 → 进入节点（phase=run）。"""
        if run["phase"] != "map_select":
            raise RunError("当前不在选路阶段")
        key = f"{row},{col}"
        m = run.get("map") or {}
        if key not in (m.get("node_types") or {}) and key != self._map_node_key(m.get("boss", {})):
            raise RunError(f"地图上不存在该节点：{key}")
        # 必须在可达列表里（fail-closed，不能跳到任意格子）
        cands = self.map_candidates(run)
        if {"row": row, "col": col} not in cands:
            raise RunError(f"节点 {key} 不可达（请从可达节点中选择）")
        # Boss 节点（boss 行）→ 进入 boss 事件
        boss_key = self._map_node_key(m.get("boss", {}))
        if key == boss_key:
            event_id = self._pick_boss_event(run)
            run["map_pos"] = {"floor": m.get("floor", 1), "row": row, "col": col, "boss": True}
        else:
            node_type = m["node_types"][key]
            elite = bool(m.get("node_elite", {}).get(key))
            event_id = self._assemble_node(run, node_type, elite)
            m["chains"][key] = event_id
            m["node_start_visited"] = len(run["visited"])  # 记录节点内链起点（防环兜底）
            run["map_pos"] = {"floor": m.get("floor", 1), "row": row, "col": col, "boss": False}
        run["phase"] = "run"
        self._enter(run, event_id)
        return self._result(run)

    def auto_select_next(self, run: dict) -> dict:
        """纯文本模式自动选路：从可达节点 PRNG 随机选一个进入（无地图 UI）。"""
        cands = self.map_candidates(run)
        if not cands:
            raise RunError("没有可达节点（地图异常）")
        pick = _rng_draw(run, cands)
        return self.map_select(run, row=pick["row"], col=pick["col"])

    def _assemble_node(self, run: dict, node_type: str, elite: bool) -> str:
        """从事件池按节点类型装配一个事件链入口（map_anchor/enter 事件）。"""
        active = set(self._active_themes(run))
        used = set(run["visited"])
        candidates = []
        weights = []
        for eid, e in self.events.items():
            tid = e.get("theme_id", "")
            if tid not in active:
                continue
            if not (e.get("map_anchor") or e.get("trigger", {}).get("type") == "enter"):
                continue
            rt = e.get("room_types") or []
            if node_type == "safe" and "safe" not in rt:
                continue
            if node_type == "treasure" and "treasure" not in rt:
                continue
            if node_type == "corridor" and not ("corridor" in rt or "safe" in rt):
                continue
            if node_type in ("encounter", "safe", "treasure", "corridor"):
                pass
            if elite and node_type == "encounter":
                if e.get("intensity") != "high":
                    continue
            if e.get("once") and eid in used:
                continue
            candidates.append(eid)
            weights.append(self._mix_weight(tid))
        if not candidates:
            raise RunError(f"节点类型 {node_type} 无可用事件（事件池不足）")
        # 优先装配尚未访问过的事件；只有该类型候选耗尽后才复用，降低同局撞车。
        fresh_pairs = [(eid, weight) for eid, weight in zip(candidates, weights) if eid not in used]
        if fresh_pairs:
            candidates = [eid for eid, _ in fresh_pairs]
            weights = [weight for _, weight in fresh_pairs]
        return _rng_draw(run, candidates, weights=weights)

    def _pick_boss_event(self, run: dict) -> str:
        """抽一个 boss 事件（kind=boss 或 boss:true），优先未用过的。"""
        active = set(self._active_themes(run))
        cands = [eid for eid, e in self.events.items()
                 if e.get("theme_id") in active and (e.get("kind") == "boss" or e.get("boss"))]
        if not cands:
            raise RunError("没有可用的 Boss 事件")
        used = set(run["visited"])
        fresh = [c for c in cands if c not in used]
        pool = fresh or cands
        weights = [self._mix_weight(self.events[c].get("theme_id", "")) for c in pool]
        return _rng_draw(run, pool, weights=weights)

    def is_exit_event(self, run: dict, e: dict) -> bool:
        """出口判定（T030 定稿）：room_exit 显式 / corridor+safe 推断（非节点锚点）/ 链尾无路。

        节点锚点事件（进入节点时的第一个事件）不算出口，防止「一进就离开」。
        """
        if not run.get("map_mode"):
            return False
        # 链尾：无 choices 或 ending → 强制出口
        if e.get("ending") or e.get("kind") == "ending":
            return True
        if not (e.get("choices") or []):
            return True
        # 显式 room_exit
        if e.get("room_exit") is True:
            return True
        if e.get("room_exit") is False:
            return False
        # 推断：corridor/safe 类型事件（非锚点）视为出口
        rt = set(e.get("room_types") or [])
        if rt & {"corridor", "safe"}:
            anchor = (run.get("map") or {}).get("chains", {}).get(self._map_node_key(run.get("map_pos")))
            if e["id"] != anchor:
                return True
        return False

    def _after_event(self, run: dict) -> None:
        """事件推进后的地图状态流转：出口 → 回选路 / Boss 结束 → 下一层或结局。"""
        if not run.get("map_mode"):
            return
        m = run.get("map") or {}
        pos = run.get("map_pos") or {}
        # 非终层的 ending（Boss 结局事件）：当作层间结算叙事 → 进入下一层
        if run["phase"] == "ending":
            floor = int(pos.get("floor", m.get("floor", 1)))
            cur_ev = self.events.get(run.get("event_id") or "", {})
            is_boss = bool(cur_ev.get("kind") == "boss" or cur_ev.get("boss"))
            # 死亡结局（HP≤0）不推进；boss/ending 且非终层 → 下一层
            if run.get("ending_id") != "failure" and floor < run["floors"] and (is_boss or pos.get("boss")):
                run["phase"] = "map_select"
                run["ending_id"] = None
                run["map"] = self._new_floor_state(run, floor + 1)
                run["map_pos"] = None
            return
        ev = self.current_event(run)
        # 节点内链长兜底：超过 MAP_CHAIN_MAX 个事件强制视为出口（防作者环/死循环）
        chain_len = len(run["visited"]) - int(m.get("node_start_visited", 0))
        if chain_len > MAP_CHAIN_MAX:
            run["phase"] = "map_select"
            if pos and not pos.get("boss"):
                m["visited_nodes"].append(self._map_node_key(pos))
            return
        # 终点节点（boss 行节点）完成 → 层结算/结局
        if pos.get("boss") or (pos and self._map_node_key(pos) == self._map_node_key(m.get("boss", {}))):
            floor = int(pos.get("floor", m.get("floor", 1)))
            if floor >= run["floors"]:
                run["phase"] = "ending"
                run["ending_id"] = run["event_id"]
                return
            # 进入下一层（层间结算简化版：直接生成新层，heat 保留）
            run["map"] = self._new_floor_state(run, floor + 1)
            run["map_pos"] = None
            run["phase"] = "map_select"
            return
        if self.is_exit_event(run, ev):
            # 标记节点完成
            if pos and not pos.get("boss"):
                m["visited_nodes"].append(self._map_node_key(pos))
            run["phase"] = "map_select"
            # map_pos 保持当前节点（下一行可达节点按它的出边算）

    def advance(self, run: dict, *, choice_id: str | None = None, intent_text: str | None = None) -> dict:
        """推进到下一个事件，返回结构化结果（叙事由调用方另生成）。"""
        cur = self.current_event(run)
        if run["phase"] == "ending":
            raise RunError("本局已结束，不能继续推进")
        next_id = self._resolve_next(run, cur, choice_id, intent_text)
        if next_id not in self.events:
            # fail-closed：未知/不可达事件，拒绝推进，绝不猜
            raise RunError(f"未知事件 id：{next_id!r}（已拒绝，不推进）")
        self._enter(run, next_id)
        self._after_event(run)
        return self._result(run)

    # ------------------------------------------------------------------ 推进
    def _resolve_next(self, run: dict, cur: dict, choice_id, intent_text) -> str:
        if choice_id:
            for c in cur.get("choices") or []:
                if c.get("id") != choice_id:
                    continue
                for k, v in (c.get("requires") or {}).items():
                    if run["flags"].get(k) != v:
                        raise RunError(f"选项未满足条件：{k}（需要 {v!r}）")
                for k, v in (c.get("set") or {}).items():
                    run["flags"][k] = v
                # 记录选择（叙事记忆来源：T030 #7）
                run["choice_log"].append({
                    "choice_id": choice_id,
                    "label": c.get("label") or choice_id,
                    "next_event_id": c["next_event_id"],
                })
                return c["next_event_id"]
            raise RunError(f"当前事件没有该选项：{choice_id!r}")
        if intent_text:
            # 意图兜底：匹配事件 intents（hint/intent 关键词命中），否则走 reachable
            matched = None
            for it in cur.get("intents") or []:
                kw = str(it.get("hint") or it.get("intent") or "")
                if kw and kw in intent_text:
                    matched = it.get("next")
                    break
            if matched:
                return matched
            reach = cur.get("reachable_event_ids") or []
            if reach:
                return self._pick_event(run, reach)
            # 没有意图表也没有可达集：自由输入不可用
            raise RunError("当前事件不支持自由输入（请选择选项）")
        # 无 choice 无 intent：若有可达集则自由移动，否则报错
        reach = cur.get("reachable_event_ids") or []
        if reach:
            return self._pick_event(run, reach)
        raise RunError("当前事件无路可走（既无选项也无可达集）")

    def _enter(self, run: dict, event_id: str) -> None:
        e = self.events[event_id]
        run["event_id"] = event_id
        run["turn_index"] += 1
        # 楼层/房间：地图模式由 map_pos 派生；线性模式兼容旧语义（tier 驱动层数）
        if run.get("map_pos"):
            run["floor_index"] = int(run["map_pos"]["floor"])
            run["room_index"] = int(run["map_pos"].get("row", 1))
        else:
            tier = int(e.get("tier", 1) or 1)
            run["floor_index"] = tier
            same_tier = [v for v in run["visited"] if self.events.get(v, {}).get("tier", 1) == tier]
            run["room_index"] = len(same_tier) + 1
        run["visited"].append(event_id)
        # 副作用：stat_delta + flags + 淫纹机制
        delta = e.get("stat_delta") or {}
        self._apply_stat_delta(run, delta)
        for k, v in (e.get("flags_set") or {}).items():
            run["flags"][k] = v
        for k in e.get("flags_unset") or []:
            run["flags"].pop(k, None)
        self._apply_mark_effects(run, e)
        self._mark_auto(run, e)
        # 结局判定
        if int(run["run_state"]["hp"]) <= 0:
            run["phase"] = "ending"
            run["ending_id"] = "failure"
        elif e.get("ending") or e.get("kind") == "ending":
            run["phase"] = "ending"
            run["ending_id"] = event_id
        run["updated_at"] = int(time.time())

    def _apply_stat_delta(self, run: dict, delta: dict) -> None:
        rs = run["run_state"]
        if not isinstance(delta, dict):
            return
        if "hp" in delta:
            rs["hp"] = max(0, min(MAX_HP, int(rs["hp"]) + int(delta["hp"])))
        if "will" in delta:
            rs["will"] = max(0, min(MAX_WILL, int(rs["will"]) + int(delta["will"])))
        for k, v in delta.items():
            if k in ("hp", "will", "heat", "orgasm_count"):
                # heat/orgasm_count 由 mark 字段管，stat_delta 写了也不进 affinity（防双轨）
                continue
            # 其余键视为「<theme>_affinity」之类的亲和增量
            if isinstance(v, (int, float)):
                rs["affinity"][k] = int(rs["affinity"].get(k, 0)) + int(v)

    # ------------------------------------------------------------------ 淫纹机制（底座设定 §4）
    def _apply_mark_effects(self, run: dict, e: dict) -> None:
        """应用事件声明的淫纹效果。

        事件可选字段 mark: { heat_delta, heat_set, kindle, flare, feed, orgasm }
        - heat_delta: heat 增量（可负）；heat_set: 绝对值（两者同时给时 heat_set 优先）
        - kindle: 点燃（置 mark_kindled）
        - orgasm: 高潮计数 +1；达到 KINDLE_ORGASM_AT 且未点燃 → 自动点燃
        - flare: 显式进入发作（置 mark_flaring）
        - feed: 喂饱——熄发作（heat 回落由 heat_set 或默认 HEAT_COOL_VALUE 处理）
        """
        m = e.get("mark") or {}
        if not isinstance(m, dict) or not m:
            return
        rs = run["run_state"]
        heat = int(rs.get("heat", 0))
        if isinstance(m.get("heat_set"), (int, float)):
            heat = int(m["heat_set"])
        elif isinstance(m.get("heat_delta"), (int, float)):
            heat += int(m["heat_delta"])
        rs["heat"] = max(0, min(HEAT_MAX, heat))
        if m.get("orgasm"):
            rs["orgasm_count"] = int(rs.get("orgasm_count", 0)) + 1
            if rs["orgasm_count"] >= KINDLE_ORGASM_AT and not run["flags"].get("mark_kindled"):
                run["flags"]["mark_kindled"] = True
        if m.get("kindle"):
            run["flags"]["mark_kindled"] = True
        if m.get("feed"):
            if not isinstance(m.get("heat_set"), (int, float)):
                rs["heat"] = HEAT_COOL_VALUE
            run["flags"]["mark_flaring"] = False
        if m.get("flare"):
            run["flags"]["mark_flaring"] = True

    def _mark_auto(self, run: dict, e: dict) -> None:
        """进入事件后的自动淫纹逻辑：安全室降温（防刷）+ 发作/熄灭判定（滞回 + 按层阈值）。

        显式 mark.flare/feed 的事件（发作/喂饱本身）不走自动判定，由 effects 权威决定。
        """
        m = e.get("mark") or {}
        if not isinstance(m, dict):
            m = {}
        rs = run["run_state"]
        heat = int(rs.get("heat", 0))
        # 安全处/篝火旁默认降温；上一事件也是 safe 则不重复减（防 entry↔safe 无限刷）
        if "safe" in (e.get("room_types") or []) and not e.get("mark"):
            prev_id = run["visited"][-2] if len(run["visited"]) >= 2 else None
            prev_e = self.events.get(prev_id) if prev_id else None
            prev_is_safe = bool(prev_e and "safe" in (prev_e.get("room_types") or []))
            if not prev_is_safe:
                rs["heat"] = max(0, min(HEAT_MAX, heat - HEAT_SAFE_ROOM_COOL))
        # 自动发作/熄灭（带滞回 + 按层阈值）；显式 flare/feed 事件跳过
        if run["flags"].get("mark_kindled") and not m.get("flare") and not m.get("feed"):
            flare_at = HEAT_FLARE_BY_FLOOR.get(int(run.get("floor_index", 1)), HEAT_FLARE_AT)
            if not run["flags"].get("mark_flaring") and heat >= flare_at:
                run["flags"]["mark_flaring"] = True
            elif run["flags"].get("mark_flaring") and heat < flare_at - HEAT_HYSTERESIS:
                run["flags"]["mark_flaring"] = False

    # ------------------------------------------------------------------ 读取
    def current_event(self, run: dict) -> dict:
        if not run.get("event_id"):
            raise RunError("run 尚未进入事件")
        e = self.events.get(run["event_id"])
        if not e:
            raise RunError(f"run 指向的当前事件已不存在：{run['event_id']!r}")
        return e

    def _result(self, run: dict) -> dict:
        e = self.current_event(run)
        return {
            "event_id": e["id"],
            "event": e,
            "phase": run["phase"],
            "ending_id": run["ending_id"],
            "floor_index": run["floor_index"],
            "room_index": run["room_index"],
            "turn_index": run["turn_index"],
            "run_state": dict(run["run_state"]),
            "flags": dict(run["flags"]),
            "feedback_on_enter": (e.get("feedback") or {}).get("on_enter") or [],
            "feedback_on_exit": (e.get("feedback") or {}).get("on_exit") or [],
        }

    def snapshot(self, run: dict) -> dict:
        """返回 run 的可序列化快照（供存档/展示）。"""
        return {
            "preset_id": run["preset_id"],
            "active_themes": list(run["active_themes"]),
            "mix_policy": run["mix_policy"],
            "seed": run["seed"],
            "floors": run["floors"],
            "floor_index": run["floor_index"],
            "room_index": run["room_index"],
            "map_mode": run.get("map_mode", False),
            "map_pos": run.get("map_pos"),
            "event_id": run["event_id"],
            "turn_index": run["turn_index"],
            "run_state": dict(run["run_state"]),
            "flags": dict(run["flags"]),
            "visited": list(run["visited"]),
            "choice_log": list(run["choice_log"]),
            "phase": run["phase"],
            "ending_id": run["ending_id"],
            "rng_state": run["rng_state"],
            "created_at": run["created_at"],
            "updated_at": run["updated_at"],
        }

    @staticmethod
    def restore(snap: dict) -> dict:
        """从快照恢复 run 对象。"""
        run = dict(snap)
        run.setdefault("run_state", {"hp": HP_START, "will": WILL_START, "affinity": {}})
        run["run_state"].setdefault("heat", 0)
        run["run_state"].setdefault("orgasm_count", 0)
        run.setdefault("flags", {})
        run.setdefault("visited", [])
        run.setdefault("choice_log", [])
        run.setdefault("map_mode", False)
        run.setdefault("map_pos", None)
        return run
