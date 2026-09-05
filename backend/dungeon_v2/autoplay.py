# -*- coding: utf-8 -*-
"""自动通关工具（验收 §七.8）：python -m backend.dungeon_v2.autoplay [--pack DIR] [--seeds N]

对每个目标（sink / escape / stay / defeat）用固定策略推进，从 seed=1 起逐个尝试，
找到第一个达成目标的 seed 就报告路径。不接设备（纯引擎），不写存档。

退出码：0 = 四个目标都可达且无死循环；1 = 有目标不可达。
策略 = {事件 id: 选项序号}（1-based）。检定失败自动折叠进 fail 分支，策略不需要处理。
defeat 目标用 debug_state={"hp": 1} 开局（引擎测试口，不经 HTTP 暴露），再额外尝试自然掉血路径。
"""
from __future__ import annotations

import sys
from pathlib import Path

from .engine import Engine
from .errors import DungeonError
from .loader import Pack, known_patterns_default, load_pack

MAX_STEPS = 80

POLICIES: dict[str, dict[str, int]] = {
    # 全 yield：ma 5+15+10+15+25+40 = 110 ≥ 100 → E012 选1 结算 crossed → E015
    "sink": {"E001": 2, "E002": 1, "E003": 2, "E004": 2, "E005": 1, "E007": 1, "E008": 2, "E009": 2,
             "E010": 1, "E011": 1, "E012": 1, "E015": 1, "E006": 3, "E016": 1, "E013": 1, "E014": 1},
    # 拿骰子、少沾污染、Boss 硬扛（str 14）→ E013
    "escape": {"E001": 1, "E002": 2, "E005": 2, "E016": 1, "E006": 3, "E008": 2, "E011": 2, "E012": 2,
               "E013": 1, "E010": 1, "E009": 2, "E007": 1, "E003": 1, "E004": 2, "E014": 1, "E015": 1},
    # 同上但 Boss 滚下肉座（dex 14）→ E014
    "stay": {"E001": 1, "E002": 2, "E005": 2, "E016": 1, "E006": 3, "E008": 2, "E011": 2, "E012": 3,
             "E014": 1, "E010": 1, "E009": 2, "E007": 1, "E003": 1, "E004": 2, "E013": 1, "E015": 1},
    # 找掉血：E001 选3(-1) → E004 选1(-1) → E007 选2(-1) → E009 选2(-1) → E010 选2(-1) → E012 选2(-3)
    "defeat": {"E001": 3, "E002": 1, "E003": 1, "E004": 1, "E005": 1, "E007": 2, "E009": 2, "E011": 3,
               "E006": 3, "E008": 1, "E010": 2, "E012": 2, "E016": 1, "E013": 1, "E014": 1, "E015": 1},
}


def play(pack: Pack, seed: int, policy: dict[str, int], target: str, debug_state: dict | None = None,
         max_steps: int = MAX_STEPS) -> dict:
    """按策略跑一局。返回 {ok, reason, path, ending, defeats, crossed, steps, state}。"""
    eng = Engine(pack)
    run = eng.new_run(seed, debug_state=debug_state)
    path = [run.event_id]
    seen_defeat = False
    for _ in range(max_steps):
        if run.phase != "playing":
            break
        eid = run.event_id
        choice = policy.get(eid)
        if choice is None:
            return _res(False, f"策略未覆盖事件 {eid}", path, run, seen_defeat)
        try:
            out = eng.advance(run, choice)
        except DungeonError as exc:
            if exc.code == "require_unmet":
                # 门槛选项不可用：换第一条可用的
                ev = eng.current_event(run)
                views = eng.choice_gate_view(run, ev)
                alt = next((i + 1 for i, v in enumerate(views) if not v["disabled"]), None)
                if alt is None:
                    return _res(False, f"{eid} 所有选项都被门槛锁住", path, run, seen_defeat)
                out = eng.advance(run, alt)
            else:
                return _res(False, f"{eid} 推进异常：{exc}", path, run, seen_defeat)
        if out.defeat:
            seen_defeat = True
            path.append(f"[败北→{run.event_id}]")
            if target == "defeat":
                return _res(True, "hp 归零 → 清理 → 回安全区", path, run, True)
            continue
        if out.ending:
            path.append(f"[{out.ending}]")
            ok = out.ending == target
            return _res(ok, f"结局 {out.ending}", path, run, seen_defeat)
        path.append(run.event_id)
    return _res(False, f"超过 {max_steps} 步仍未结束（疑似死循环）", path, run, seen_defeat)


def _res(ok: bool, reason: str, path: list, run, seen_defeat: bool) -> dict:
    return {
        "ok": ok, "reason": reason, "path": list(path), "ending": run.ending, "defeats": run.defeats,
        "seen_defeat": seen_defeat, "crossed": run.state.crossed_gate, "steps": run.turn,
        "state": {"hp": run.state.hp, "ma": run.state.ma, "yin_hua": run.state.yin_hua,
                  "stage": run.state.mark_stage, "dice": run.state.dice,
                  "str": run.state.str, "dex": run.state.dex, "int": run.state.int},
        "seed": run.seed,
    }


def find_seed(pack: Pack, target: str, seeds=range(1, 401), debug_state: dict | None = None) -> dict | None:
    policy = POLICIES[target]
    for s in seeds:
        r = play(pack, s, policy, target, debug_state=debug_state)
        if r["ok"]:
            return r
    return None


def default_pack_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "backend" / "tests" / "fixtures" / "dungeon_v2" / "abyss"


def main(argv: list[str] | None = None) -> int:
    from .cli import utf8_console
    utf8_console()
    argv = list(sys.argv[1:] if argv is None else argv)
    pack_dir = default_pack_dir()
    n_seeds = 400
    if "--pack" in argv:
        pack_dir = Path(argv[argv.index("--pack") + 1])
    if "--seeds" in argv:
        n_seeds = int(argv[argv.index("--seeds") + 1])
    import logging
    logging.getLogger("ai-for-coyote.dungeon_v2.loader").setLevel(logging.ERROR)
    pack = load_pack(pack_dir, known_patterns_default())
    all_ok = True
    summary: dict[str, str] = {}
    for target in ("escape", "stay", "sink"):
        r = find_seed(pack, target, range(1, n_seeds + 1))
        if r is None:
            all_ok = False
            summary[target] = f"不可达（试了 {n_seeds} 个 seed）"
            print(f"[{target}] {summary[target]}")
            continue
        summary[target] = f"可达 seed={r['seed']} steps={r['steps']} crossed={r['crossed']}"
        print(f"[{target}] seed={r['seed']} steps={r['steps']} crossed={r['crossed']} state={r['state']}")
        print("   路径: " + " → ".join(r["path"]))
    # 败北：debug hp=1 必达；自然掉血路径顺带找一下（找不到不算失败）
    r = find_seed(pack, "defeat", range(1, 51), debug_state={"hp": 1})
    if r is None:
        all_ok = False
        summary["defeat"] = "不可达（debug hp=1 仍未触发）"
        print(f"[defeat] {summary['defeat']}")
    else:
        summary["defeat"] = f"可达 (debug hp=1) seed={r['seed']} defeats={r['defeats']}"
        print(f"[defeat] (debug hp=1) seed={r['seed']} defeats={r['defeats']} state={r['state']}")
        print("   路径: " + " → ".join(r["path"]))
    rn = find_seed(pack, "defeat", range(1, n_seeds + 1))
    if rn is None:
        print(f"[defeat] 自然掉血：{n_seeds} 个 seed 内未出现（hp 10 起，掉血源有限；不计失败）")
    else:
        summary["defeat"] += f"；自然掉血 seed={rn['seed']} steps={rn['steps']}"
        print(f"[defeat] 自然掉血 seed={rn['seed']} steps={rn['steps']} 路径: " + " → ".join(rn["path"]))
    # 四行结局汇总（D6 R3：escape / stay / sink / defeat 各一行，便于人工回归）
    print("----- 结局汇总 -----")
    for target in ("escape", "stay", "sink", "defeat"):
        print(f"结局 {target:<7} {summary.get(target, '未测')}")
    print("自动通关：" + ("OK" if all_ok else "FAIL"))
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
