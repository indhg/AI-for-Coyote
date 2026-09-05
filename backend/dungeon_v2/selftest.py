# -*- coding: utf-8 -*-
"""自测：python -m backend.dungeon_v2.selftest [--pack DIR] [--probe SEED]

覆盖验收 §七：校验器 / 变体跨进程复现 / 骰子区间与 ed6 归零复现 / effects 钳制 /
沉·逃·留三结局 / 未 crossed 重遇 / 净化窗口 / 败北 / 急停闸 / 存档 / render 契约 /
体感执行器（真 SafetyManager，dry_run）/ 禁词 0 泄漏。

退出码：0 = 全部 PASS；1 = 有 FAIL。
--probe SEED：只打印变体探针（每个多版事件 visit 1..4 的变体索引 + 文本 sha256 前 12 位）后退出 0，
              用于两个独立进程对比（T04 自己会起两个子进程比对）。
"""
from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

from . import constants as C
from .autoplay import POLICIES, find_seed, play
from .checks import roll_bonus
from .effects import apply_effects
from .engine import Engine
from .errors import DungeonError
from .lint_words import scan_engine_en, scan_tree
from .loader import known_patterns_default, load_pack, load_tree
from .narrative import select_variant
from .rng import RunRNG, variant_index
from .runtime import DungeonRuntime
from .schema import validate_tree
from .state import RunState
from .map_gen import assert_gen_constraints, generate_map
from .map_logic import compute_states, render_map

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PACK_DIR = PROJECT_ROOT / "backend" / "tests" / "fixtures" / "dungeon_v2" / "abyss"
MAP_PACK_DIR = PROJECT_ROOT / "backend" / "tests" / "fixtures" / "dungeon_v2" / "abyss_map"

# ---------- 环境 ----------
try:
    from ..safety import SafetyManager  # type: ignore
    SAFETY_KIND = "SafetyManager(真)"
except Exception:  # noqa: BLE001
    SafetyManager = None  # type: ignore
    SAFETY_KIND = "FakeSafety(壳缺失)"

try:
    from ..waveforms import WAVEFORMS  # type: ignore
except Exception:  # noqa: BLE001
    WAVEFORMS = {}


class FakeSafety:
    """壳文件缺失时的最小替身（只在独立目录跑 selftest 时用到；仓库内一定用真 SafetyManager）。"""

    def __init__(self, cfg) -> None:
        self.estop_active = False
        self.dry_run = True
        self.presets = cfg.get("presets", {})

    def cap_for(self, ch):
        return 100

    def validate(self, action):
        if self.estop_active:
            return False, "急停中，拒绝一切设备动作", None
        op = action.get("op")
        kind = {"temp_strength": "temp", "hold_strength": "hold", "add_strength": "add",
                "pulse": "pulse", "clear": "clear", "stop": "stop"}.get(op)
        if kind is None:
            return False, f"未知 op: {op!r}", None
        cmd = {"kind": kind, "channel": action.get("channel")}
        if kind in ("temp", "hold"):
            cmd["value"] = min(100, int(action.get("value", 0)))
        if kind in ("temp", "pulse"):
            cmd["duration_s"] = float(action.get("duration_s", 3))
        if kind == "pulse":
            cmd["pattern"] = action.get("pattern")
        if kind == "add":
            cmd["delta"] = int(action.get("delta", 0))
        return True, "ok", cmd

    def record(self, cmd):
        pass

    def estop(self):
        self.estop_active = True
        return []

    def resume(self):
        self.estop_active = False


def make_cfg(lang: str = "zh") -> dict:
    presets = {}
    for key, meta in WAVEFORMS.items():
        presets[str(meta["cn"])] = {"waveform": key, "label": meta["cn"], "frames": meta["frames"],
                                    "default_duration_s": 5.0, "max_duration_s": 10.0, "category": "经典波形"}
    return {
        "safety": {"channels": {"A": {"max_strength": 200}, "B": {"max_strength": 200}},
                   "max_temp_duration_s": 10, "max_strength_step": 40, "overheat_reduce_to": 20},
        "playback": {"frame_ms": 100, "min_duration_s": 3, "max_duration_s": 10, "loop_batch_s": 30, "loop_overlap_s": 0.3},
        "presets": presets, "ui": {}, "app": {"dry_run": True}, "character": {"lang": lang},
        "device_channels": {}, "dungeon": {"ai_narrative": False},
    }


def make_safety(cfg):
    if SafetyManager is not None:
        return SafetyManager(cfg)
    return FakeSafety(cfg)


def make_runtime(tmp_root: Path, lang: str = "zh") -> DungeonRuntime:
    """runtime 需要 project_root/content/pack/dungeon/<pack>：把包目录软拷到临时根。"""
    import shutil
    dst = tmp_root / "content" / "pack" / "dungeon" / "abyss"
    if not dst.exists():
        shutil.copytree(PACK_DIR, dst)
    cfg = make_cfg(lang)
    return DungeonRuntime(cfg, None, make_safety(cfg), tmp_root)


def run_async(coro):
    return asyncio.run(coro)


def sink_choices() -> list[tuple[str, int]]:
    return [("E001", 2), ("E002", 1), ("E003", 2), ("E004", 2), ("E005", 1), ("E007", 1),
            ("E008", 2), ("E011", 1), ("E012", 1), ("E015", 1)]


# ============================================================ 测试 ============================================================
def t01_pack_valid(ctx):
    tree = load_tree(PACK_DIR)
    res = validate_tree(tree, known_patterns_default())
    assert res.ok, "校验失败：\n" + res.report()
    assert len(tree["events"]) == 16, f"事件数 {len(tree['events'])} != 16"
    assert set(tree["events"]) == {f"E{i:03d}" for i in range(1, 17)}
    ctx["tree"] = tree
    ctx["pack"] = load_pack(PACK_DIR, known_patterns_default())
    return f"16 事件 OK，{len(res.warnings)} warning"


def t02_validator_rejects(ctx):
    base = ctx["tree"]
    cases = []

    def mut(name, fn):
        t = copy.deepcopy(base)
        fn(t)
        res = validate_tree(t, known_patterns_default())
        assert not res.ok, f"坏样例「{name}」竟然通过了校验"
        assert all(e.strip() for e in res.errors), "错误文本为空"
        cases.append((name, res.errors[0]))

    mut("未知 band", lambda t: t["events"]["E003"].__setitem__("band", "floor2"))
    mut("属性检定缺 fail", lambda t: t["events"]["E003"]["choices"][0].pop("fail"))
    mut("next 悬空", lambda t: t["events"]["E002"]["choices"][0].__setitem__("next", "E099"))
    mut("fail 指向属性检定（递归）", lambda t: t["events"]["E003"]["choices"][0].__setitem__("fail", {"choice": 3}))
    mut("未知 effect 键", lambda t: t["events"]["E004"]["choices"][1].__setitem__("effects", {"heat": 5}))
    mut("结局前驱非 boss", lambda t: t["events"]["E006"]["choices"][2].__setitem__("next", "E013"))
    mut("feedback 无核心词", lambda t: t["events"]["E008"].__setitem__("feedback", "轻轻的"))
    mut("mo_hua_gte 未启用", lambda t: t["events"]["E006"]["choices"][0].__setitem__("require", {"mo_hua_gte": 50}))
    mut("非结局用 next=end", lambda t: t["events"]["E008"]["choices"][0].__setitem__("next", "end"))
    mut("安全区 feedback 缺清理", lambda t: t["events"]["E006"].__setitem__("feedback", "停顿"))
    mut("bindings 清理缺 stop", lambda t: t["bindings"]["rhythm"]["清理"].__setitem__("actions", [{"op": "clear"}]))
    mut("bindings 用 pulse_hold", lambda t: t["bindings"]["rhythm"]["持续"]["actions"].append({"op": "pulse_hold", "channel": "A", "pattern": "呼吸"}))
    mut("bindings 未知波形", lambda t: t["bindings"]["rhythm"]["试探"]["actions"].append({"op": "pulse", "channel": "A", "pattern": "不存在的波", "duration_s": 3}))
    mut("manifest format 错", lambda t: t["manifest"].__setitem__("format", "dungeon_v1"))
    mut("孤立节点", lambda t: (t["events"]["E005"]["choices"][1].__setitem__("next", "E006")))  # E016 不可达
    mut("连续三场同 species", lambda t: t["events"]["E012"].__setitem__("species", "触手"))  # E010触手→E011触手→E012触手
    return f"{len(cases)} 个坏样例全部被拒；首条：{cases[0][1][:60]}…"


def t03_variant_index(ctx):
    assert variant_index(1, "E002", 1, 1) == 0 and variant_index(1, "E002", 1, 0) == 0
    a = variant_index(12345, "E006", 2, 3)
    b = variant_index(12345, "E006", 2, 3)
    assert a == b and 0 <= a < 3
    ref = int.from_bytes(hashlib.sha256(b"12345|E006|2").digest()[:8], "big") % 3
    assert a == ref, "与任务书公式不一致"
    seen = {variant_index(s, "E006", v, 3) for s in range(50) for v in range(1, 5)}
    assert seen == {0, 1, 2}, f"变体分布未覆盖全部索引：{seen}"
    ev = ctx["pack"].event("E006")
    sel = select_variant(7, ev, 1)
    assert sel["count"] == 3 and sel["text"] in ([ev["seed"]] + ev["variants"])
    single = select_variant(7, ctx["pack"].event("E001"), 5)
    assert single["index"] == 0 and single["source"] == "seed"
    return "SHA-256 变体索引 OK（公式一致、覆盖 0..N-1、单版恒基底）"


def probe(seed: int) -> str:
    pack = load_pack(PACK_DIR, None)
    lines = []
    for eid in sorted(pack.events):
        ev = pack.events[eid]
        if not ev.get("variants"):
            continue
        for v in range(1, 5):
            sel = select_variant(seed, ev, v)
            h = hashlib.sha256(sel["text"].encode("utf-8")).hexdigest()[:12]
            lines.append(f"{eid} visit{v} idx={sel['index']}/{sel['count']} {h}")
    return "\n".join(lines)


def t04_cross_process(ctx):
    seed = 20260903
    local = probe(seed)
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1", PYTHONHASHSEED="")
    outs = []
    for hs in ("1", "2"):  # 两个独立进程，且故意用不同 hash seed
        env["PYTHONHASHSEED"] = hs
        p = subprocess.run([sys.executable, "-m", "backend.dungeon_v2.selftest", "--probe", str(seed), "--pack", str(PACK_DIR)],
                           cwd=str(PROJECT_ROOT), env=env, capture_output=True, text=True, encoding="utf-8")
        assert p.returncode == 0, f"probe 子进程失败：{p.stderr[-500:]}"
        outs.append(p.stdout.strip())
    assert outs[0] == outs[1] == local.strip(), "两个进程的变体探针不一致"
    n = len(local.splitlines())
    return f"两独立进程（PYTHONHASHSEED 1/2）变体索引与文本哈希完全一致（{n} 行）"


def t05_dice(ctx):
    for dice, mx in C.DICE_MAX_BONUS.items():
        rng = RunRNG(99)
        vals = [roll_bonus(rng, dice) for _ in range(4000)]
        raws = {r["raw"] for r in vals}
        assert min(raws) == 0 and max(raws) == mx, f"{dice} 区间 {min(raws)}..{max(raws)} != 0..{mx}"
        assert raws == set(range(mx + 1)), f"{dice} 未覆盖所有面：{sorted(raws)}"
        zrate = sum(r["zeroed"] for r in vals) / len(vals)
        if dice == "ed6":
            assert 0.12 <= zrate <= 0.18, f"ed6 归零率 {zrate:.3f} 偏离 15%"
        else:
            assert zrate == 0
    # 归零路径可复现：找一个 seed 使首掷归零，再用同 seed 重放
    zero_seed = next(s for s in range(1, 10000) if roll_bonus(RunRNG(s), "ed6")["zeroed"])
    r1 = roll_bonus(RunRNG(zero_seed), "ed6")
    r2 = roll_bonus(RunRNG(zero_seed), "ed6")
    assert r1 == r2 and r1["zeroed"]
    # 状态序列化后继续掷 = 不序列化继续掷
    a = RunRNG(5)
    [a.randint(0, 6) for _ in range(3)]
    b = RunRNG.from_state(json.loads(json.dumps(a.get_state())))
    assert [a.randint(0, 6) for _ in range(20)] == [b.randint(0, 6) for _ in range(20)]
    ctx["ed6_zero_seed"] = zero_seed
    return f"d1=0/1 d4=0~4 d6=0~6 ed6=0~6 归零率≈15%；归零复现 seed={zero_seed}；rng_state 往返一致"


def t06_effects_clamp(ctx):
    rng = RunRNG(1)
    s = RunState(ma=5, hp=9, str=20, yin_hua=98, mark_stage="none")
    apply_effects(s, [{"ma": -10}, {"hp": 5}, {"str": 1}, {"yin_hua": 5}, {"stage_down": True}], 1, rng)
    s.clamp_all()
    assert (s.ma, s.hp, s.str, s.yin_hua, s.mark_stage) == (0, 10, 20, 100, "none"), s.to_dict()
    s = RunState()
    apply_effects(s, {"stage_appear": True}, 1, rng)
    assert s.mark_stage == "appear"
    apply_effects(s, {"stage_bud": True, "stage_form": True}, 1, rng)   # 顺序覆盖 → form
    assert s.mark_stage == "form"
    apply_effects(s, {"stage_down": True}, 1, rng)
    assert s.mark_stage == "appear"
    # visit_n_eq 门
    s = RunState()
    sm = apply_effects(s, {"ma": 10, "visit_n_eq": 1}, 2, rng)
    assert s.ma == 0 and sm["skipped"] and "visit_n_eq" in sm["skipped"][0]["reason"]
    apply_effects(s, {"ma": 10, "visit_n_eq": 1}, 1, rng)
    assert s.ma == 10
    # 成长只在 visit 1；污染每次
    s = RunState(dex=5)
    apply_effects(s, {"dex": 1, "ma": 2}, 2, rng)
    assert s.dex == 5 and s.ma == 2
    apply_effects(s, {"dex": 1, "ma": 2}, 1, rng)
    assert s.dex == 6 and s.ma == 4
    # dice_gain
    s = RunState()
    got = set()
    for seed in range(60):
        s.dice = "d1"
        sm = apply_effects(s, {"dice_gain": True}, 1, RunRNG(seed))
        assert s.dice in C.DICE_DROP_POOL and sm["dice_gain"] == s.dice
        got.add(s.dice)
    assert got == set(C.DICE_DROP_POOL), f"掉落池未覆盖：{got}"
    sm = apply_effects(RunState(), {"ability_up": {"id": "x"}}, 1, rng)
    assert sm["skipped"] and sm["skipped"][0]["reason"] == "ability_not_in_first_batch"
    # hp 不降穿 0 / ma 不降穿 0
    s = RunState(hp=1, ma=3)
    apply_effects(s, {"hp": -5, "ma": -50}, 1, rng)
    s.clamp_all()
    assert s.hp == 0 and s.ma == 0
    return "钳制/阶段覆盖/visit_n_eq/成长门/dice_gain/ability 忽略 全部 OK"


def t07_sink_path(ctx):
    eng = Engine(ctx["pack"])
    run = eng.new_run(1)
    assert run.event_id == "E001" and run.state.dice == "d1" and 1 <= run.state.str <= 10
    for eid, c in sink_choices():
        assert run.event_id == eid, f"期望在 {eid}，实际 {run.event_id}"
        out = eng.advance(run, c)
    assert out.ending == "sink" and run.phase == "locked" and run.state.crossed_gate
    assert run.state.ma == 110, f"ma={run.state.ma}"
    assert run.state.mark_stage == "set", run.state.mark_stage
    assert out.cleanup, "结局必须触发清理"
    try:
        eng.advance(run, 1)
        raise AssertionError("locked 后仍能推进")
    except DungeonError as exc:
        assert exc.code == "run_locked"
    # crossed 判定日志
    gate = [e for e in run.log if e.get("gate_check")]
    assert gate and gate[-1]["gate_check"]["crossed"] is True
    return f"全 yield → ma=110、crossed、E015 沉没锁定；locked 后 advance 拒绝（[run_locked]）"


def t08_uncrossed_gate(ctx):
    eng = Engine(ctx["pack"])
    run = eng.new_run(3)
    for eid, c in [("E001", 1), ("E002", 2), ("E005", 2), ("E016", 2), ("E006", 3), ("E008", 2), ("E011", 2)]:
        assert run.event_id == eid, (eid, run.event_id)
        eng.advance(run, c)
    assert run.event_id == "E012"
    out = eng.advance(run, 1)              # ma 40 <100
    assert out.gate_checked and not out.crossed and not run.state.crossed_gate
    assert run.state.mark_stage == "form" and run.event_id == "E012" and run.visit_n == 2
    out = eng.advance(run, 1)              # ma 80
    assert not out.crossed and run.event_id == "E012" and run.visit_n == 3
    out = eng.advance(run, 1)              # ma 120 → crossed
    assert out.crossed and run.event_id == "E015"
    return "E012 选1 ma<100 → 仅成形、留在主巢（visit_n 递增）；第三次 ma=120 → crossed → E015"


def t09_three_endings(ctx):
    pack = ctx["pack"]
    res = {}
    for target in ("sink", "escape", "stay"):
        r = find_seed(pack, target, range(1, 401))
        assert r is not None, f"{target} 400 seed 内不可达"
        assert r["steps"] < 80
        res[target] = r["seed"]
    # 逃/留 的 run 必须 ended（可再开），且 crossed=False
    r = play(pack, res["escape"], POLICIES["escape"], "escape")
    assert r["ending"] == "escape" and not r["crossed"]
    r = play(pack, res["stay"], POLICIES["stay"], "stay")
    assert r["ending"] == "stay" and not r["crossed"]
    return f"三结局可达：sink seed={res['sink']} escape seed={res['escape']} stay seed={res['stay']}（均 <80 步）"


def t10_defeat(ctx):
    eng = Engine(ctx["pack"])
    run = eng.new_run(11, debug_state={"hp": 1, "str": 20, "dex": 20})
    out = eng.advance(run, 3)                       # E001 选3 hp-1 → 0
    assert out.defeat and out.cleanup and run.event_id == "E006" and run.defeats == 1 and run.state.hp == 0
    assert run.last_exit and "祭坛" in run.last_exit
    try:
        eng.advance(run, 1)                         # 净化需 appear
        raise AssertionError("stage none 竟可净化")
    except DungeonError as exc:
        assert exc.code == "require_unmet"
    out = eng.advance(run, 3)                       # hp 0 但无掉血 → 不重复败北
    assert not out.defeat and run.event_id == "E008"
    eng.advance(run, 2)                             # → E011
    eng.advance(run, 3)                             # dex 20+d1 ≥12 → escape → E006 (dex 检定成功)
    assert run.event_id == "E006"
    out = eng.advance(run, 2)                       # 歇 hp+2 → E003
    assert run.state.hp == 2 and run.event_id == "E003"
    out = eng.advance(run, 3)                       # str 20 kill → E005
    assert run.event_id == "E005" and out.check and out.check["success"]
    eng.advance(run, 1)                             # E007
    out = eng.advance(run, 2)                       # hp-1 → 1 → E009
    out = eng.advance(run, 2)                       # E009 选2 hp-1 → 0 → 败北
    assert out.defeat and run.event_id == "E006" and run.defeats == 2
    return "hp→0 清理+回 E006（覆盖 next），hp=0 不掉血不重复败北，再掉血再败北；二次败北 OK"


def t11_purge_window(ctx):
    eng = Engine(ctx["pack"])
    run = eng.new_run(21, debug_state={"dex": 20})
    # ma：E003 5 + E004 15 + E005 10 + E007 15 + E010 20×3 = 105（E011 选3 dex 20 必成功逃回 E006，绕开 E012）
    seq = [("E001", 1), ("E002", 1), ("E003", 2), ("E004", 2), ("E005", 1), ("E007", 1), ("E008", 1),
           ("E010", 3), ("E011", 3), ("E006", 3), ("E008", 1), ("E010", 3), ("E011", 3),
           ("E006", 3), ("E008", 1), ("E010", 3), ("E011", 3)]
    for eid, c in seq:
        assert run.event_id == eid, (eid, run.event_id)
        eng.advance(run, c)
    assert run.event_id == "E006" and run.state.ma >= 100 and not run.state.crossed_gate, run.state.to_dict()
    assert run.state.mark_stage == "appear"
    ma0 = run.state.ma
    out = eng.advance(run, 1)                       # 净化：appear→bud, ma-10
    assert run.state.mark_stage == "bud" and run.state.ma == ma0 - 10 and run.event_id == "E006"
    try:
        eng.advance(run, 1)
        raise AssertionError("bud 竟可再净化")
    except DungeonError as exc:
        assert exc.code == "require_unmet"
    return f"ma={ma0}≥100 未 crossed 合法；E006 净化 stage appear→bud、ma-10；bud 后门槛拒绝"


def t12_estop(ctx):
    with tempfile.TemporaryDirectory() as td:
        rt = make_runtime(Path(td))
        run_async(rt.start(seed=1))
        rt.safety.estop_active = True
        try:
            run_async(rt.advance(choice_id="1"))
            raise AssertionError("急停中竟能推进")
        except DungeonError as exc:
            assert exc.code == "estop" and "急停" in str(exc)
        # 急停中体感全部被安全层拒绝
        ex, dr = run_async(rt.executor.run([{"op": "pulse", "channel": "A", "pattern": "呼吸", "duration_s": 3}]))
        assert not ex and dr and "急停" in dr[0]["reason"]
        rt.safety.estop_active = False
        res = run_async(rt.advance(choice_id="1"))
        assert res["event"]["id"] == "E002"
    return "急停中 advance → [estop] 拒绝；体感动作全 dropped；解除后恢复"


def t13_save_load(ctx):
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        rt = make_runtime(root)
        run_async(rt.start(seed=77))
        for _, c in sink_choices()[:7]:              # 走到 E011
            run_async(rt.advance(choice_id=c))
        assert rt.run.event_id == "E011"
        path = rt.save("slotA")
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
        assert doc["format"] == C.SAVE_FORMAT and doc["seed"] == 77 and "rng_state" in doc
        snap_before = rt.run.snapshot()
        # 原局继续（消耗 RNG：E011 选3 dex 检定）
        r_orig = run_async(rt.advance(choice_id="3"))
        # 读档到新 runtime 继续同样选择
        rt2 = make_runtime(root)
        res = run_async(rt2.load("slotA"))
        assert res["event"]["id"] == "E011" and rt2.run.snapshot() == snap_before
        r_load = run_async(rt2.advance(choice_id="3"))
        assert r_orig["outcome"]["check"] == r_load["outcome"]["check"], "读档后骰子与原局不一致"
        assert r_orig["run"]["event_id"] == r_load["run"]["event_id"]
        # 变体一致（跨读档文本稳定）
        assert r_orig["narrative"]["text"] == r_load["narrative"]["text"]
        # 旧档拒绝
        legacy = root / "data" / "saves" / "dungeon_v2" / "old.json"
        legacy.write_text(json.dumps({"run_state": {"heat": 3, "will": 5}}), encoding="utf-8")
        try:
            run_async(rt2.load("old"))
            raise AssertionError("旧档竟被接受")
        except DungeonError as exc:
            assert exc.code == "save_format"
        try:
            rt2.save("../evil")
            raise AssertionError("非法槽名竟被接受")
        except DungeonError as exc:
            assert exc.code == "bad_slot"
    return "存档含 format/seed/rng_state；读档快照一致、续掷一致、文本一致；旧档 [save_format] 拒绝"


def t14_render_contract(ctx):
    with tempfile.TemporaryDirectory() as td:
        rt = make_runtime(Path(td))
        res = run_async(rt.start(seed=5))
        for k in ("run", "event", "narrative", "feedback", "executed", "dropped", "map"):
            assert k in res, f"render 缺 {k}"
        ev = res["event"]
        for k in ("id", "title", "theme_id", "kind", "content_level", "tier", "choices", "free_input"):
            assert k in ev, f"event 缺 {k}"
        assert ev["theme_id"] == "abyss" and ev["free_input"] is False
        assert ev["content_level"] == 1 and ev["tier"] == 1          # E001 low/entry
        assert all(set(c) >= {"id", "label"} for c in ev["choices"])
        assert "hint" in res["feedback"] and res["narrative"]["source"] in ("seed", "variant")
        run = res["run"]
        for k in ("yin_hua", "e_duo", "ma", "ma_cap", "str", "dex", "int", "hp", "mp", "mark_stage",
                  "crossed_gate", "defected", "dice", "ability", "flags", "seed"):
            assert k in run, f"run 缺 {k}"
        assert "heat" not in run and "will" not in run and "rng_state" not in run
        # 映射表逐事件
        pack = ctx["pack"]
        for eid, e in pack.events.items():
            assert C.CONTENT_LEVEL_BY_INTENSITY[e["intensity"]] in range(5)
            assert C.TIER_BY_BAND[e["band"]] in range(1, 6)
        # 门槛选项 disabled + 后端拒绝
        for _, c in sink_choices()[:5]:
            run_async(rt.advance(choice_id=c))
        # 现在在 E007；直接测 E006 视图：另开一局到 E006
        rt2 = make_runtime(Path(td))
        run_async(rt2.start(seed=5))
        for c in (1, 2, 2, 2):                                        # E001→E002→E005→E016→E006
            r = run_async(rt2.advance(choice_id=c))
        assert r["event"]["id"] == "E006"
        c1 = r["event"]["choices"][0]
        assert c1["disabled"] is True and "disabled_reason" in c1
        try:
            run_async(rt2.advance(choice_id="1"))
            raise AssertionError("门槛未满足竟通过")
        except DungeonError as exc:
            assert exc.code == "require_unmet"
        # 结局后 choices 为空
        rt3 = make_runtime(Path(td))
        run_async(rt3.start(seed=1))
        for _, c in sink_choices():
            r = run_async(rt3.advance(choice_id=c))
        assert r["event"]["choices"] == [] and r["run"]["phase"] == "locked" and r["outcome"]["ending"] == "sink"
        assert any(x["action"].get("op") == "stop" for x in r["executed"]), "结局未执行清理 stop"
        assert rt3.to_state()["active"] is False
    return "render 字段齐全、映射正确、门槛 disabled+后端拒绝、结局清理 stop 已执行"


def t15_feedback_executor(ctx):
    with tempfile.TemporaryDirectory() as td:
        rt = make_runtime(Path(td))
        assert isinstance(rt.executor.send, type(None))
        res = run_async(rt.start(seed=2))
        # E001 「无或试探」→ 无 + 试探：应有 executed（dry_run，sent=False），无 dropped
        assert res["dropped"] == [], res["dropped"]
        assert res["executed"], "E001 试探应有动作"
        assert all(x["sent"] is False for x in res["executed"])
        assert res["feedback"]["hint"] == "试探"
        for x in res["executed"]:
            a = x["action"]
            if a.get("op") in ("temp_strength", "hold_strength"):
                assert 0 <= a["value"] <= 100
        # mid 持续：E001→E002→E003（试探→持续）
        run_async(rt.advance(choice_id="1"))
        r = run_async(rt.advance(choice_id="1"))
        ops = [x["action"]["op"] for x in r["executed"]]
        assert "hold_strength" in ops and "pulse" in ops and r["dropped"] == [], (ops, r["dropped"])
        # 假 send 记录真机调用路径（dry_run=False）
        sent_cmds = []

        async def fake_send(cmd):
            sent_cmds.append(cmd)
            return True
        rt.executor.send = fake_send
        rt.safety.dry_run = False
        r = run_async(rt.advance(choice_id="2"))    # E003 yield → E004 持续
        assert sent_cmds and all("kind" in c for c in sent_cmds)
        assert all(x["sent"] is True for x in r["executed"])
        rt.safety.dry_run = True
        # EN
        rt_en = make_runtime(Path(td), lang="en")
        r = run_async(rt_en.start(seed=2))
        assert r["feedback"]["hint"] == "tease"
        labels = [x["label"] for x in r["executed"]]
        assert any(l.startswith("A ") or l.startswith("clear") for l in labels), labels
    return f"{SAFETY_KIND}：validate→send→record 路径 OK，dry_run 不发真机，EN 走 describe_en/hint"


def t16_forbidden_words(ctx):
    hits = scan_tree(ctx["tree"]) + scan_engine_en()
    assert not hits, "禁词泄漏：\n" + "\n".join(hits)
    return "seed/variants/note/feedback/choices/flags/theme/bindings/base_setting/EN 文案 0 泄漏"


def t17_state_and_restart(ctx):
    with tempfile.TemporaryDirectory() as td:
        rt = make_runtime(Path(td))
        st = rt.to_state()
        assert st["active"] is False and st["run"] is None
        assert [p["id"] for p in st["packs"]] == ["abyss"] and st["packs"][0]["event_count"] == 16
        assert set(st["packs"][0]) >= {"id", "title", "themes", "event_count"}
        try:
            run_async(rt.advance(choice_id="1"))
            raise AssertionError("无局竟可推进")
        except DungeonError as exc:
            assert exc.code == "no_run"
        run_async(rt.start(active_themes=["abyss"], seed="abc"))
        assert rt.to_state()["active"] is True
        try:
            run_async(rt.advance(text="自由输入"))
            raise AssertionError("自由输入竟被接受")
        except DungeonError as exc:
            assert exc.code == "free_input_disabled"
        rt.restart()
        assert rt.to_state()["active"] is False
        try:
            run_async(rt.start(active_themes=["no_such"]))
            raise AssertionError("未知主题竟开局")
        except DungeonError as exc:
            assert exc.code == "pack_not_found"
    return "to_state 契约 OK；no_run / free_input_disabled / pack_not_found 错误码 OK；restart OK"


def t18_dice_drop_e016(ctx):
    pack = ctx["pack"]
    got = {}
    for seed in range(1, 200):
        eng = Engine(pack)
        run = eng.new_run(seed)
        for c in (1, 2, 2):                          # E001→E002→E005→E016
            eng.advance(run, c)
        assert run.event_id == "E016" and run.state.dice == "d1"
        out = eng.advance(run, 1)
        assert run.state.dice in C.DICE_DROP_POOL and out.effects["dice_gain"] == run.state.dice
        got.setdefault(run.state.dice, seed)
        if len(got) == 3:
            break
    assert set(got) == set(C.DICE_DROP_POOL), got
    # 重访 E016 不再掉（visit_n_eq）
    eng = Engine(pack)
    run = eng.new_run(got["d6"])
    for c in (1, 2, 2, 1):
        eng.advance(run, c)
    assert run.state.dice == "d6" and run.event_id == "E006"
    eng.advance(run, 2)                               # → E003
    eng.advance(run, 2)                               # yield → E004
    eng.advance(run, 2)                               # yield → E005 (visit 2)
    assert run.event_id == "E005" and run.visit_n == 2
    eng.advance(run, 2)                               # → E016 visit 2
    run.state.dice = "d4"
    out = eng.advance(run, 1)
    assert run.state.dice == "d4" and out.effects["dice_gain"] is None and out.effects["skipped"]
    # ed6 归零在检定中：找 seed 使 E003 选1 检定 zeroed
    found = None
    for seed in range(1, 3000):
        eng = Engine(pack)
        run = eng.new_run(seed)
        eng.advance(run, 1)
        eng.advance(run, 1)                           # E003
        run.state.dice = "ed6"
        out = eng.advance(run, 1)
        if out.check and out.check["zeroed"]:
            assert out.check["total"] == 0 and not out.check["success"] and out.folded and out.effective_index == 2
            found = seed
            break
    assert found is not None, "3000 seed 内未复现 ed6 归零"
    eng = Engine(pack)
    run = eng.new_run(found)
    eng.advance(run, 1)
    eng.advance(run, 1)
    run.state.dice = "ed6"
    out2 = eng.advance(run, 1)
    assert out2.check["zeroed"] and out2.check["total"] == 0
    return f"E016 掉骰覆盖 d4/d6/ed6（seed {got}），重访不掉；ed6 归零→total 0 折叠 fail 分支，seed={found} 复现"


def t19_check_growth_and_log(ctx):
    eng = Engine(ctx["pack"])
    run = eng.new_run(8, debug_state={"dex": 20})
    eng.advance(run, 1)
    eng.advance(run, 1)                               # E003
    out = eng.advance(run, 1)                         # dex 20 → 必成功 → escape → dex+1 (visit1)
    assert out.check["success"] and run.state.dex == 20 and run.state.ma == 2  # dex 钳 20
    logrec = run.log[-2]
    assert logrec["type"] == "advance" and logrec["check"]["attr"] == "dex" and logrec["check"]["dice"] == "d1"
    assert 0 <= logrec["check"]["bonus"] <= 1
    # 失败折叠：str 1 + d1 <8
    eng = Engine(ctx["pack"])
    run = eng.new_run(8, debug_state={"str": 1})
    eng.advance(run, 1)
    eng.advance(run, 1)
    out = eng.advance(run, 3)                         # str 检定必失败 → 折叠选2 yield
    assert not out.check["success"] and out.folded and out.effective_index == 2
    assert out.settlement == "yield" and out.estop_overrides and run.event_id == "E004"
    assert run.state.ma == 5 and run.state.yin_hua == 3 and run.state.str == 1
    return "检定成功→成长 +1（钳 20）；失败→折叠 fail.choice（effects/next/estop 全用被折叠项），日志含掷点"



def make_map_runtime(tmp_root: Path, lang: str = "zh") -> DungeonRuntime:
    import shutil
    dst = tmp_root / "content" / "pack" / "dungeon" / "abyss_map"
    if not dst.exists():
        shutil.copytree(MAP_PACK_DIR, dst)
    # also copy chain pack so coexistence discover works
    cdst = tmp_root / "content" / "pack" / "dungeon" / "abyss"
    if not cdst.exists():
        shutil.copytree(PACK_DIR, cdst)
    cfg = make_cfg(lang)
    return DungeonRuntime(cfg, None, make_safety(cfg), tmp_root)


def _map_pack():
    return load_pack(MAP_PACK_DIR, known_patterns_default())


def _finish_node(eng: Engine, run, prefer: int = 1):
    """结算当前节点直到 awaiting_move 或 ended/locked。prefer=1-based choice。"""
    guard = 0
    while run.phase == "playing" and run.map and not run.map.get("awaiting_move"):
        guard += 1
        if guard > 20:
            raise AssertionError("node settle loop")
        ev = eng.current_event(run)
        n = len(ev.get("choices") or [])
        if n < 1:
            raise AssertionError("no choices")
        # 避开必败选项：优先 prefer，否则 1
        cid = prefer if prefer <= n else 1
        # 若当前是 boss 且 prefer 指向 defeat（hp-10），测试方自己控制
        eng.advance(run, cid)


def _walk_to_boss(eng: Engine, run, *, hp_boost: bool = True):
    if hp_boost:
        run.state.hp = 10
        run.state.str = 20
        run.state.dex = 20
        run.state.int = 20
    _finish_node(eng, run, prefer=1)
    guard = 0
    while run.phase == "playing":
        guard += 1
        if guard > 80:
            raise AssertionError("walk loop")
        if run.map["current"] == run.map["terminus"]["boss"] and not run.map.get("awaiting_move"):
            return
        if run.map.get("awaiting_move"):
            st = compute_states(run.map, run.state)
            # 优先沿可达且通向 boss 的节点：简单 BFS 选下一步
            boss = run.map["terminus"]["boss"]
            edges = run.map["edges"]
            adj = {}
            for e in edges:
                adj.setdefault(e["from"], []).append(e["to"])
            # 从 boss 反推
            rev = {}
            for e in edges:
                rev.setdefault(e["to"], []).append(e["from"])
            can = set()
            stack = [boss]
            while stack:
                n = stack.pop()
                if n in can:
                    continue
                can.add(n)
                stack.extend(rev.get(n, []))
            reach = [nid for nid, s in st.items() if s["state"] == "reachable"]
            pick = None
            for nid in reach:
                if nid in can:
                    pick = nid
                    break
            if pick is None and reach:
                pick = reach[0]
            if pick is None:
                raise AssertionError("no reachable toward boss")
            eng.move(run, pick)
        else:
            _finish_node(eng, run, prefer=1)


def t20_map_generator(ctx):
    g1 = generate_map(12345)
    g2 = generate_map(12345)
    g3 = generate_map(99999)
    assert g1["floors"] == g2["floors"] and g1["nodes"] == g2["nodes"] and g1["edges"] == g2["edges"]
    assert g1["seed_label"] == g2["seed_label"]
    assert g1 != g3 or g1["seed_label"] != g3["seed_label"]
    # 结构不等（允许极小概率撞车，再换种子）
    if g1["floors"] == g3["floors"] and g1["edges"] == g3["edges"]:
        g3 = generate_map(424242)
    assert g1["edges"] != g3["edges"] or g1["floors"] != g3["floors"]
    for seed in (1, 2, 3, 42, 100, 777, 2026):
        errs = assert_gen_constraints(generate_map(seed))
        assert not errs, (seed, errs)
    # SHA-256 口径：seed_label 为 hex 大写
    assert len(g1["seed_label"]) == 5 and all(c in "0123456789ABCDEF" for c in g1["seed_label"])
    assert all(nd["room"] != "corridor" for nd in g1["nodes"])
    return f"同seed一致 / 异seed差异 / 约束7种子全绿 / seed_label={g1["seed_label"]}"


def t21_map_move_gates(ctx):
    pack = _map_pack()
    eng = Engine(pack)
    run = eng.new_run(7, debug_state={"hp": 1, "str": 20, "dex": 20, "int": 20})
    assert run.mode == "map" and run.map and not run.map["awaiting_move"]
    # 未 awaiting 时 move 拒绝
    try:
        eng.move(run, run.map["current"])
        raise AssertionError("not_awaiting 未触发")
    except DungeonError as exc:
        assert exc.code == "not_awaiting"
    _finish_node(eng, run, 1)
    assert run.map["awaiting_move"]
    st = compute_states(run.map, run.state)
    # locked 拒绝
    locked = [nid for nid, s in st.items() if s["state"] == "locked"]
    assert locked
    try:
        eng.move(run, locked[0])
        raise AssertionError("locked 竟可 move")
    except DungeonError as exc:
        assert exc.code == "not_reachable"
    # gated：人为给一个 reachable 邻居加门槛
    reach = [nid for nid, s in st.items() if s["state"] == "reachable"]
    assert reach
    # 找任意出边目标设 gate
    tgt = reach[0]
    for nd in run.map["nodes"]:
        if nd["id"] == tgt:
            nd["gate"] = {"hp_gte": 99}
            break
    try:
        eng.move(run, tgt)
        raise AssertionError("gated 竟可 move")
    except DungeonError as exc:
        assert exc.code == "require_unmet" and "hp" in str(exc).lower() or "HP" in str(exc) or "hp" in str(exc)
    # 去掉门槛后可走
    for nd in run.map["nodes"]:
        if nd["id"] == tgt:
            nd["gate"] = None
            break
    eng.move(run, tgt)
    assert run.map["current"] == tgt and not run.map["awaiting_move"]
    # estop via runtime
    with tempfile.TemporaryDirectory() as td:
        rt = make_map_runtime(Path(td))
        run_async(rt.start(active_themes=["abyss_map"], seed=3))
        # settle entry
        while rt.run.phase == "playing" and not rt.run.map.get("awaiting_move"):
            run_async(rt.advance(choice_id="1"))
        rt.safety.estop_active = True
        st2 = compute_states(rt.run.map, rt.run.state)
        rch = [nid for nid, s in st2.items() if s["state"] == "reachable"]
        try:
            run_async(rt.move(node_id=rch[0]))
            raise AssertionError("estop 未拦 move")
        except DungeonError as exc:
            assert exc.code == "estop"
    return "move not_awaiting/locked/gated/estop/reachable OK"


def t22_map_endings_and_defeat(ctx):
    pack = _map_pack()
    # 三结局各一次
    for prefer, kind in ((1, "escape"), (2, "stay"), (3, "sink")):
        eng = Engine(pack)
        run = eng.new_run(50 + prefer, debug_state={"hp": 10, "str": 20, "dex": 20, "int": 20})
        _walk_to_boss(eng, run)
        assert run.map["current"] == run.map["terminus"]["boss"]
        # 在 boss 事件内：选 prefer；str/dex 20 对 TN14 必过（+d1）
        out = eng.advance(run, prefer)
        # 进入结局事件或已结束
        if run.phase == "playing":
            out2 = eng.advance(run, 1)
            assert out2.ending == kind or run.ending == kind
        assert run.ending == kind
        assert run.phase in ("ended", "locked")
        reached = {e["kind"]: e["reached"] for e in run.map["terminus"]["endings"]}
        assert reached[kind] is True
    # 败北终局
    eng = Engine(pack)
    run = eng.new_run(60, debug_state={"hp": 10, "str": 20, "dex": 20, "int": 20})
    _walk_to_boss(eng, run)
    out = eng.advance(run, 4)  # hp-10
    assert out.defeat and run.phase == "ended" and run.ending is None
    assert run.defeats == 1
    # 无回流：不能再 move/advance 玩
    try:
        eng.advance(run, 1)
        raise AssertionError("ended 后还能 advance")
    except DungeonError as exc:
        assert exc.code == "run_ended"
    return "三结局各达 + 败北终局（裁决21）OK"


def t23_map_render_save(ctx):
    pack = _map_pack()
    eng = Engine(pack)
    run = eng.new_run(8, debug_state={"hp": 10, "str": 20, "dex": 20})
    _finish_node(eng, run, 1)
    mv = render_map(run.map, run.state)
    for k in ("mode", "floors", "current", "awaiting_move", "nodes", "edges", "path", "terminus", "seed_label"):
        assert k in mv, k
    assert mv["mode"] == "map"
    n0 = mv["nodes"][0]
    for k in ("id", "floor", "col", "room", "band", "state", "revealed"):
        assert k in n0, k
    assert n0["state"] in ("current", "reachable", "gated", "visited", "bypassed", "locked")
    # save/load map + chain 旧档
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        rt = make_map_runtime(root)
        res = run_async(rt.start(active_themes=["abyss_map"], seed=8))
        assert res["map"]["mode"] == "map"
        while rt.run.phase == "playing" and not rt.run.map.get("awaiting_move"):
            run_async(rt.advance(choice_id="1"))
        path = rt.save("mapA")
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
        assert doc["version"] == C.SAVE_VERSION and doc["run"].get("mode") == "map" and doc["run"].get("map")
        snap = rt.run.to_dict(with_rng=False)
        rt2 = make_map_runtime(root)
        res2 = run_async(rt2.load("mapA"))
        assert res2["map"]["mode"] == "map"
        assert rt2.run.map["current"] == snap["map"]["current"]
        assert rt2.run.map["path"] == snap["map"]["path"]
        # chain 旧档（version=1 无 map）仍可读
        rt3 = make_runtime(root)  # abyss chain only in its own copy — use map runtime which has both
        run_async(rt3.start(active_themes=["abyss"], seed=1))
        # force write v1-like by rewriting after save
        p = rt3.save("chainB")
        doc = json.loads(Path(p).read_text(encoding="utf-8"))
        doc["version"] = 1
        doc["run"].pop("map", None)
        doc["run"]["mode"] = "chain"
        Path(p).write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
        res3 = run_async(rt3.load("chainB"))
        assert res3["map"]["mode"] == "chain"
    # 证据 JSON
    evidence_dir = PROJECT_ROOT / "协作交接" / "地牢" / "结论" / "D25-evidence"
    # PROJECT_ROOT is AI-for-Coyote; 协作交接 is sibling under CoyoteWithAI
    evidence_dir = PROJECT_ROOT.parent / "协作交接" / "地牢" / "结论" / "D25-evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    (evidence_dir / "render_map_sample.json").write_text(
        json.dumps({"map": mv, "run_mode": run.mode, "event_id": run.event_id}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return f"render§6.1 OK；save/load map+chain v1 OK；sample→{evidence_dir / 'render_map_sample.json'}"


TESTS = [t01_pack_valid, t02_validator_rejects, t03_variant_index, t04_cross_process, t05_dice,
         t06_effects_clamp, t07_sink_path, t08_uncrossed_gate, t09_three_endings, t10_defeat,
         t11_purge_window, t12_estop, t13_save_load, t14_render_contract, t15_feedback_executor,
         t16_forbidden_words, t17_state_and_restart, t18_dice_drop_e016, t19_check_growth_and_log,
         t20_map_generator, t21_map_move_gates, t22_map_endings_and_defeat, t23_map_render_save]


def main(argv: list[str] | None = None) -> int:
    global PACK_DIR
    from .cli import utf8_console
    utf8_console()
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--pack" in argv:
        PACK_DIR = Path(argv[argv.index("--pack") + 1])
    if "--probe" in argv:
        print(probe(int(argv[argv.index("--probe") + 1])))
        return 0
    import logging
    logging.getLogger("ai-for-coyote.dungeon_v2.loader").setLevel(logging.ERROR)  # warning 由 validate_pack 报，这里不重复刷
    print(f"dungeon_v2 selftest  pack={PACK_DIR}  safety={SAFETY_KIND}")
    ctx: dict = {}
    failed = 0
    for fn in TESTS:
        name = fn.__name__
        try:
            msg = fn(ctx)
            print(f"PASS {name}: {msg}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"FAIL {name}: {exc}")
            traceback.print_exc(limit=3)
            if fn is t01_pack_valid:
                print("包加载失败，后续测试跳过")
                break
    print(f"结果：{len(TESTS) - failed}/{len(TESTS)} PASS → {'OK' if not failed else 'FAIL'}")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
