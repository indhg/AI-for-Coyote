# -*- coding: utf-8 -*-
"""map 模式确定性路网生成（D25 / fable D26 §6.5）。

- 结构决策一律 SHA-256 稳定哈希（禁内置 hash()）
- floors 8–12（含入口行与 Boss 行，不含结局行）
- 每层 2–4 节点；入口行 1–3；Boss 行恰好 1
- room 从可用集抽取，永不生成 corridor
- 有向边只连相邻层；无死局（从 current/入口可达 Boss）
- 节点 id 与事件 id 解耦；事件按 room 从内容池绑定
"""
from __future__ import annotations

import hashlib
from typing import Any


# 中间层可抽 room（无 corridor / boss / ending）
MAP_ROOM_POOL = ("encounter", "rest", "treasure", "trap", "nest", "gate")
ENTRY_ROOM_POOL = ("rest", "gate", "rest")  # 偏 rest
# room → 内容池事件候选（pack 内必须存在）
DEFAULT_ROOM_EVENTS: dict[str, tuple[str, ...]] = {
    "encounter": ("E101", "E102"),
    "rest": ("E201",),
    "treasure": ("E301",),
    "trap": ("E401",),
    "nest": ("E501",),
    "gate": ("E001",),
    "boss": ("E901",),
}


def stable_digest(*parts: Any) -> bytes:
    payload = "|".join("" if p is None else str(p) for p in parts).encode("utf-8")
    return hashlib.sha256(payload).digest()


def stable_u64(*parts: Any) -> int:
    return int.from_bytes(stable_digest(*parts)[:8], "big")


def stable_int(*parts: Any, lo: int, hi: int) -> int:
    """闭区间 [lo, hi] 稳定整数。"""
    if hi < lo:
        raise ValueError(f"stable_int bad range {lo}..{hi}")
    span = hi - lo + 1
    return lo + (stable_u64(*parts) % span)


def stable_choice(seq, *parts: Any):
    if not seq:
        raise ValueError("stable_choice empty")
    return seq[stable_u64(*parts) % len(seq)]


def seed_label(seed: int) -> str:
    """4–6 位展示用短哈希。"""
    return hashlib.sha256(f"seed_label|{int(seed)}".encode("utf-8")).hexdigest()[:5].upper()


def band_for_floor(floor: int, floors: int) -> str:
    """按层深映射 5 band（入口/浅/中/深/Boss）。"""
    if floor <= 0:
        return "entry"
    if floor >= floors - 1:
        return "end"  # Boss 行用 end band（与 kind=boss 共存：boss 事件自身 band 另定）
    # 中间层：按比例切 mid/upper/lower
    frac = floor / max(1, floors - 2)
    if frac < 0.34:
        return "mid"
    if frac < 0.67:
        return "upper"
    return "lower"


def _pick_cols(n: int, seed: int, floor: int) -> list[int]:
    """同层 col 0..3 不重复。"""
    pool = [0, 1, 2, 3]
    # 稳定洗牌
    for i in range(len(pool) - 1, 0, -1):
        j = stable_u64(seed, "col_shuf", floor, i) % (i + 1)
        pool[i], pool[j] = pool[j], pool[i]
    return sorted(pool[:n])


def _assign_event(room: str, seed: int, node_id: str, room_events: dict[str, tuple[str, ...]]) -> str:
    cands = room_events.get(room) or DEFAULT_ROOM_EVENTS.get(room) or ("E101",)
    return stable_choice(cands, seed, "evt", node_id, room)


def generate_map(
    seed: int,
    *,
    room_events: dict[str, tuple[str, ...]] | None = None,
    event_titles: dict[str, str] | None = None,
) -> dict:
    """生成一整局路网。返回可序列化 dict（入档）。

    结构：
      floors, seed_label, nodes[{id,floor,col,room,band,event_id,gate?,title?}],
      edges[{from,to}], current, path, awaiting_move,
      terminus{boss,endings[{kind,reached}]},
      bypassed[]（运行期维护）
    """
    seed = int(seed)
    room_events = room_events or dict(DEFAULT_ROOM_EVENTS)
    event_titles = event_titles or {}

    floors = stable_int(seed, "floors", lo=8, hi=12)
    nodes: list[dict] = []
    by_floor: dict[int, list[str]] = {}

    for f in range(floors):
        if f == 0:
            n = stable_int(seed, "n", f, lo=1, hi=3)
        elif f == floors - 1:
            n = 1
        else:
            n = stable_int(seed, "n", f, lo=2, hi=4)
        cols = _pick_cols(n, seed, f)
        ids_here: list[str] = []
        for i, col in enumerate(cols):
            nid = f"N{f}_{col}"
            if f == floors - 1:
                room = "boss"
                band = "end"
            elif f == 0:
                room = stable_choice(ENTRY_ROOM_POOL, seed, "room", nid)
                # 入口至少一个 rest：若本层抽完后无 rest，把第一个改成 rest
                band = "entry"
            else:
                room = stable_choice(MAP_ROOM_POOL, seed, "room", nid)
                band = band_for_floor(f, floors)
                if band == "end":
                    band = "lower"
            eid = _assign_event(room, seed, nid, room_events)
            gate = None
            # ~15% 中层节点加软门槛（演示 gated）；保证不堵死主链：见连边后修剪
            if f not in (0, floors - 1) and (stable_u64(seed, "gate?", nid) % 100) < 15:
                gate = {"hp_gte": 3}
            node = {
                "id": nid,
                "floor": f,
                "col": col,
                "room": room,
                "band": band,
                "event_id": eid,
                "revealed": True,  # StS 口径全揭示
                "title": event_titles.get(eid),
                "gate": gate,
            }
            nodes.append(node)
            ids_here.append(nid)
        # 入口行保证至少 1 个 rest
        if f == 0 and not any(nd["room"] == "rest" for nd in nodes if nd["floor"] == 0):
            nodes_on = [nd for nd in nodes if nd["floor"] == 0]
            nodes_on[0]["room"] = "rest"
            nodes_on[0]["event_id"] = _assign_event("rest", seed, nodes_on[0]["id"], room_events)
            nodes_on[0]["title"] = event_titles.get(nodes_on[0]["event_id"])
        by_floor[f] = ids_here

    # ---- 边：先铺一条贯穿主链，再补随机出边，保证无死局 ----
    edges: list[dict] = []
    edge_set: set[tuple[str, str]] = set()

    def add_edge(a: str, b: str) -> None:
        key = (a, b)
        if key in edge_set:
            return
        # 仅相邻层
        fa = next(nd["floor"] for nd in nodes if nd["id"] == a)
        fb = next(nd["floor"] for nd in nodes if nd["id"] == b)
        if fb != fa + 1:
            return
        edge_set.add(key)
        edges.append({"from": a, "to": b})

    # 主链：每层选一个代表节点（稳定），串到 Boss
    spine: list[str] = []
    for f in range(floors):
        spine.append(stable_choice(by_floor[f], seed, "spine", f))
    for i in range(len(spine) - 1):
        add_edge(spine[i], spine[i + 1])

    # 每层每个非 Boss 节点至少 1 条出边
    for f in range(floors - 1):
        nxt = by_floor[f + 1]
        for nid in by_floor[f]:
            outs = [e for e in edges if e["from"] == nid]
            if not outs:
                add_edge(nid, stable_choice(nxt, seed, "must_out", nid))
            # 额外 0–2 条
            extra = stable_int(seed, "extra", nid, lo=0, hi=min(2, len(nxt)))
            for k in range(extra):
                add_edge(nid, stable_choice(nxt, seed, "extra_to", nid, k))

    # 保证下一层每个节点至少 1 入边（除已连通外补边）
    for f in range(1, floors):
        prev = by_floor[f - 1]
        for nid in by_floor[f]:
            ins = [e for e in edges if e["to"] == nid]
            if not ins:
                add_edge(stable_choice(prev, seed, "must_in", nid), nid)

    # 主链节点去掉可能堵死的高门槛：spine 上 gate 清除
    spine_set = set(spine)
    for nd in nodes:
        if nd["id"] in spine_set:
            nd["gate"] = None

    boss_id = by_floor[floors - 1][0]
    # 入口 current：优先 rest 节点，否则 spine[0]
    entry_rest = [nd["id"] for nd in nodes if nd["floor"] == 0 and nd["room"] == "rest"]
    current = entry_rest[0] if entry_rest else spine[0]

    # 可达性断言（生成期自检）
    if not _reachable_to(current, boss_id, edges):
        # 极端补救：把 current 直接挂到 spine
        if current != spine[0]:
            # 同层无边；把 current 设为 spine[0]
            current = spine[0]
        if not _reachable_to(current, boss_id, edges):
            raise RuntimeError("map_gen: failed to ensure path to boss")

    return {
        "floors": floors,
        "seed_label": seed_label(seed),
        "nodes": nodes,
        "edges": edges,
        "current": current,
        "path": [current],
        "awaiting_move": False,  # 开局先跑入口事件
        "bypassed": [],
        "terminus": {
            "boss": boss_id,
            "endings": [
                {"kind": "escape", "reached": False},
                {"kind": "stay", "reached": False},
                {"kind": "sink", "reached": False},
            ],
        },
    }


def _reachable_to(start: str, goal: str, edges: list[dict]) -> bool:
    adj: dict[str, list[str]] = {}
    for e in edges:
        adj.setdefault(e["from"], []).append(e["to"])
    seen, stack = set(), [start]
    while stack:
        n = stack.pop()
        if n == goal:
            return True
        if n in seen:
            continue
        seen.add(n)
        stack.extend(adj.get(n, []))
    return False


def assert_gen_constraints(graph: dict) -> list[str]:
    """返回违规列表（空=通过）。供自测。"""
    errs: list[str] = []
    floors = int(graph["floors"])
    if not (8 <= floors <= 12):
        errs.append(f"floors={floors} not in 8..12")
    nodes = graph["nodes"]
    edges = graph["edges"]
    by_floor: dict[int, list[dict]] = {}
    for nd in nodes:
        by_floor.setdefault(nd["floor"], []).append(nd)
        if nd["room"] == "corridor":
            errs.append(f"corridor at {nd['id']}")
        if not (0 <= nd["col"] <= 3):
            errs.append(f"bad col {nd['id']}")
    for f in range(floors):
        row = by_floor.get(f, [])
        cols = [n["col"] for n in row]
        if len(cols) != len(set(cols)):
            errs.append(f"duplicate col on floor {f}")
        if f == 0 and not (1 <= len(row) <= 3):
            errs.append(f"entry count {len(row)}")
        elif f == floors - 1 and len(row) != 1:
            errs.append(f"boss row count {len(row)}")
        elif f not in (0, floors - 1) and not (2 <= len(row) <= 4):
            errs.append(f"floor {f} count {len(row)}")
        if f == floors - 1 and row and row[0]["room"] != "boss":
            errs.append("boss row not boss room")
    id_floor = {n["id"]: n["floor"] for n in nodes}
    for e in edges:
        if id_floor[e["to"]] != id_floor[e["from"]] + 1:
            errs.append(f"non-adjacent edge {e}")
    # 非 Boss 至少 1 出边
    outs = {n["id"]: 0 for n in nodes}
    for e in edges:
        outs[e["from"]] = outs.get(e["from"], 0) + 1
    boss = graph["terminus"]["boss"]
    for nid, c in outs.items():
        if nid != boss and c < 1:
            errs.append(f"no out edge {nid}")
    if not _reachable_to(graph["current"], boss, edges):
        errs.append("current cannot reach boss")
    return errs
