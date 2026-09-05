# -*- coding: utf-8 -*-
"""map 运行态：节点 state 权威计算 + move 校验辅助（D25 / D26 §6.1）。"""

from __future__ import annotations

from .checks import unmet_gates_struct
from .errors import DungeonError
from .state import RunState


NODE_STATES = ("current", "reachable", "gated", "visited", "bypassed", "locked")


def node_by_id(graph: dict, nid: str) -> dict:
    for nd in graph.get("nodes") or []:
        if nd["id"] == nid:
            return nd
    raise DungeonError("bad_node", f"节点 {nid!r} 不存在", f"node {nid!r} missing")


def neighbors_out(graph: dict, nid: str) -> list[str]:
    return [e["to"] for e in (graph.get("edges") or []) if e["from"] == nid]


def mark_ending_reached(graph: dict, kind: str) -> None:
    for e in graph.get("terminus", {}).get("endings") or []:
        if e.get("kind") == kind:
            e["reached"] = True


def compute_states(graph: dict, state: RunState) -> dict[str, dict]:
    current = graph.get("current")
    path = list(graph.get("path") or [])
    bypassed = set(graph.get("bypassed") or [])
    visited = set(path)
    cur_floor = None
    id_floor = {n["id"]: n["floor"] for n in graph.get("nodes") or []}
    if current in id_floor:
        cur_floor = id_floor[current]
    if cur_floor is not None and path:
        max_visited_floor = max(id_floor.get(pid, 0) for pid in path)
        for nd in graph["nodes"]:
            if nd["id"] in visited:
                continue
            if nd["floor"] < cur_floor or nd["floor"] < max_visited_floor:
                bypassed.add(nd["id"])

    outs = set(neighbors_out(graph, current)) if current else set()
    result: dict[str, dict] = {}
    for nd in graph.get("nodes") or []:
        nid = nd["id"]
        info: dict = {"state": "locked", "gate": None}
        if nid == current:
            info["state"] = "current"
        elif nid in bypassed:
            info["state"] = "bypassed"
        elif nid in visited:
            info["state"] = "visited"
        elif nid in outs:
            gate = nd.get("gate") or {}
            unmet = unmet_gates_struct(state, gate) if gate else []
            if unmet:
                info["state"] = "gated"
                info["gate"] = {"unmet": unmet}
            else:
                info["state"] = "reachable"
        else:
            info["state"] = "locked"
        result[nid] = info
    graph["bypassed"] = sorted(bypassed)
    return result


def apply_move(graph: dict, node_id: str, state: RunState) -> dict:
    if not graph.get("awaiting_move"):
        raise DungeonError("not_awaiting", "当前不在选路阶段（节点事件未结算完）", "not awaiting move")
    states = compute_states(graph, state)
    st = states.get(node_id)
    if st is None:
        raise DungeonError("not_reachable", f"节点 {node_id!r} 不可达", f"node {node_id!r} not reachable")
    if st["state"] == "gated":
        unmet = (st.get("gate") or {}).get("unmet") or []
        texts = [u.get("text", "") for u in unmet]
        raise DungeonError(
            "require_unmet",
            "路径门槛未满足：" + "；".join(texts),
            "path gate unmet: " + "; ".join(texts),
        )
    if st["state"] != "reachable":
        raise DungeonError(
            "not_reachable",
            f"节点 {node_id!r} 当前不可选（{st['state']}）",
            f"node {node_id!r} not reachable ({st['state']})",
        )

    cur = node_by_id(graph, graph["current"])
    tgt = node_by_id(graph, node_id)
    bypassed = set(graph.get("bypassed") or [])
    # 选定下一层后，该层本步展示的其余支路全部作废；未进入本步候选层的节点仍 locked。
    # 路网把整行作为同层候选展示，即使某条边未直接连到当前点，也不应在
    # 玩家已选定该行后继续显示成 locked 支路。
    candidate_floor = tgt["floor"]
    if candidate_floor == cur["floor"] + 1:
        for nd in graph["nodes"]:
            if nd["floor"] == candidate_floor and nd["id"] != node_id:
                bypassed.add(nd["id"])
    graph["current"] = node_id
    if not graph.get("path"):
        graph["path"] = [node_id]
    elif graph["path"][-1] != node_id:
        graph["path"].append(node_id)
    graph["bypassed"] = sorted(bypassed)
    graph["awaiting_move"] = False
    return tgt


def render_map(graph: dict, state: RunState, *, phase: str = "playing") -> dict:
    states = compute_states(graph, state)
    nodes_out = []
    for nd in graph.get("nodes") or []:
        st = states[nd["id"]]
        item = {
            "id": nd["id"],
            "floor": int(nd["floor"]),
            "col": int(nd["col"]),
            "room": nd["room"],
            "band": nd["band"],
            "state": st["state"],
            "revealed": bool(nd.get("revealed", True)),
        }
        if st["state"] in ("visited", "current") and nd.get("title"):
            item["title"] = nd["title"]
        if st["state"] == "gated" and st.get("gate"):
            item["gate"] = st["gate"]
        nodes_out.append(item)
    return {
        "mode": "map",
        "floors": int(graph["floors"]),
        "current": graph.get("current"),
        "awaiting_move": bool(graph.get("awaiting_move")),
        "nodes": nodes_out,
        "edges": [{"from": e["from"], "to": e["to"]} for e in (graph.get("edges") or [])],
        "path": list(graph.get("path") or []),
        "terminus": {
            "boss": (graph.get("terminus") or {}).get("boss"),
            "endings": list((graph.get("terminus") or {}).get("endings") or []),
        },
        "seed_label": str(graph.get("seed_label") or ""),
    }
