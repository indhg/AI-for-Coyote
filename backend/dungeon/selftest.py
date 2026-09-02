# -*- coding: utf-8 -*-
"""M2 地牢骨架自检（dry_run）。

覆盖验收点：
1. sample 主题包加载 + 入口事件正确
2. 沿 choices 打完第一层到结局
3. 多主题随机池：mixed_pool 混搭两主题 + 同 seed 可复现
4. API 失败 → 叙事回退作者 seed（fixed 模式零 API）
5. 存档/读档往返（含 RNG 状态）+ 读档后续局
6. 未知事件拒绝（fail-closed）
7. 反馈查表 + 三态提示

运行：仓库根目录下 `python -m backend.dungeon.selftest`
"""
from __future__ import annotations

import asyncio
import shutil
import tempfile
from pathlib import Path

from .engine import DungeonEngine
from .feedback import resolve_feedback
from .loader import load_pack
from .narrative import NarrativeWriter
from .save import load_run, save_run

SAMPLE = Path(__file__).resolve().parents[1] / "story_pack" / "sample"


class _FailLLM:
    async def complete(self, *a, **k):
        raise RuntimeError("模拟 API 断网")


class _OkLLM:
    async def complete(self, system, user, max_tokens=4000):
        return "（这是一段模拟的 AI 叙事扩写。）"


def _syn_manifest():
    return """\
schema: theme_pack/v1
kind: theme_pack
id: syn
title: 合成测试包
version: 0.1.0
min_app_version: 1.1.5
locale: zh-CN
content_rating: "18+"
consent_notice: 这是一个用于 M2 自检的合成测试包，包含两个主题用于验证多主题随机池与种子可复现，仅内部测试使用。
authors: [测试]
license: proprietary
device_narrative: tentacle
themes:
  - {id: aa, label: 主题A}
  - {id: bb, label: 主题B}
mix: {compatible_with: [aa, bb], mix_weight: 1.0, pool_policy: mixed_pool}
contributes: {events: events/, bindings: bindings/}
"""


def _syn_theme():
    return """\
schema: theme_identity/v1
theme_id: aa
name: 主题A
device_narrative: tentacle
content_levels: [中]
"""


def _syn_events():
    def ev(eid, title, theme, trigger, reach=None):
        r = f"\n    reachable_event_ids: [{', '.join(reach)}]" if reach else ""
        return (
            f"  - id: {eid}\n    title: {title}\n    theme_id: {theme}\n    kind: scene\n"
            f"    room_types: [corridor]\n    tier: 1\n    intensity: low\n    content_level: 中\n"
            f"    trigger: {{type: {trigger}}}\n"
            f"    narrative: {{mode: seed_and_improvise, seed: {title}}}\n{r}\n"
            f"    feedback: {{on_enter: [], on_exit: []}}\n"
        )

    return (
        "schema: theme_events/v1\nevents:\n"
        + ev("syn.entry", "入口", "aa", "enter", reach=["syn.a1", "syn.b1", "syn.a2", "syn.b2"])
        + ev("syn.a1", "A1", "aa", "choice")
        + ev("syn.a2", "A2", "aa", "choice")
        + ev("syn.b1", "B1", "bb", "choice")
        + ev("syn.b2", "B2", "bb", "choice")
    )


def _make_syn_pack(tmp: Path) -> Path:
    p = tmp / "syn"
    (p / "events").mkdir(parents=True)
    (p / "bindings").mkdir(parents=True)
    (p / "manifest.yaml").write_text(_syn_manifest(), encoding="utf-8")
    (p / "theme.yaml").write_text(_syn_theme(), encoding="utf-8")
    (p / "events" / "e.yaml").write_text(_syn_events(), encoding="utf-8")
    (p / "bindings" / "b.yaml").write_text("schema: theme_bindings/v1\nbindings: []\n", encoding="utf-8")
    return p


def main() -> int:
    passed = 0
    total = 0
    failures = []

    def check(cond, label):
        nonlocal passed, total
        total += 1
        if cond:
            passed += 1
        else:
            failures.append(label)
        print(f"  [{'PASS' if cond else 'FAIL'}] {label}")

    tmp = Path(tempfile.mkdtemp(prefix="dungeon_selftest_"))
    try:
        # ---- 1. sample 加载 + 入口 ----
        pack = load_pack(SAMPLE)
        eng = DungeonEngine({t: pack for t in pack.theme_ids})
        check(pack.theme_ids == ["tentacle"], "sample 主题包加载（theme_id=tentacle）")
        check(len(eng.entry_ids) >= 1, f"存在入口事件（{eng.entry_ids}）")

        # ---- 2. 沿 choices 打完第一层到结局 ----
        run = eng.start(active_themes=["tentacle"], mix_policy="single_theme", floors=3, seed=7)
        check(run["event_id"] == "tentacle.enc.gate", f"入口事件 = gate（实际 {run['event_id']}）")
        for cid in ["step_in", "still", "deeper", "reach"]:
            cur = eng.current_event(run)
            if cid not in [c.get("id") for c in cur.get("choices") or []]:
                check(False, f"当前事件 {cur['id']} 无选项 {cid}")
                break
            eng.advance(run, choice_id=cid)
        check(run["phase"] == "ending", f"沿 choices 到达结局（ending_id={run['ending_id']}）")
        check(run["event_id"] == "tentacle.end.tentacle", f"结局事件 = tentacle.end.tentacle（实际 {run['event_id']}）")

        # ---- 3. 多主题随机池：mixed_pool 混搭 + 同 seed 可复现 ----
        syn = load_pack(_make_syn_pack(tmp))
        seng = DungeonEngine({"aa": syn, "bb": syn})
        r1 = seng.start(active_themes=["aa", "bb"], mix_policy="mixed_pool", floors=1, seed=42)
        r2 = seng.start(active_themes=["aa", "bb"], mix_policy="mixed_pool", floors=1, seed=42)
        p1 = seng.advance(r1)["event_id"]
        p2 = seng.advance(r2)["event_id"]
        check(p1 == p2, f"同 seed=42 自由移动 → 同一事件（{p1}）")
        themes_seen = set()
        for s in range(40):
            rr = seng.start(active_themes=["aa", "bb"], mix_policy="mixed_pool", floors=1, seed=s)
            eid = seng.advance(rr)["event_id"]
            themes_seen.add(seng.events[eid]["theme_id"])
        check({"aa", "bb"} <= themes_seen, f"mixed_pool 混搭到两个主题（seen={sorted(themes_seen)}）")

        # ---- 3b. 楼层/房间生成（seed 可复现 + per_floor 单主题 + Boss 房） ----
        fp1 = seng.generate_floor_plan(seng.start(active_themes=["aa", "bb"], mix_policy="per_floor", floors=2, seed=9))
        fp2 = seng.generate_floor_plan(seng.start(active_themes=["aa", "bb"], mix_policy="per_floor", floors=2, seed=9))
        check([p["room_type"] for p in fp1] == [p["room_type"] for p in fp2], "楼层/房间生成 seed 可复现")
        check(len(fp1) == 2 * 4 + 2, f"房间数 = {len(fp1)}（2 层×4 房 + boss + 结局）")
        f1_themes = {p["theme_id"] for p in fp1 if p["floor"] == 1}
        check(len(f1_themes) == 1, f"per_floor 第 1 层单主题（{f1_themes}）")
        check(any(p["room_type"] == "boss" for p in fp1), "楼层计划含 Boss 房")

        # ---- 4. API 失败 → 回退 seed（fixed 零 API） ----
        async def _narr():
            w_fail = NarrativeWriter(llm=_FailLLM(), dm_prompt=pack.dm_prompt)
            ev = pack.event_index["tentacle.enc.wrap_arm"]
            r_fail = await w_fail.narrate(ev)
            w_ok = NarrativeWriter(llm=_OkLLM(), dm_prompt=pack.dm_prompt)
            r_ok = await w_ok.narrate(ev)
            return r_fail, r_ok

        r_fail, r_ok = asyncio.run(_narr())
        check(r_fail["source"] == "seed" and r_fail["text"].strip(), "API 失败 → 回退作者 seed（非空）")
        check(r_ok["source"] == "llm" and "模拟" in r_ok["text"], "API 正常 → 返回 LLM 扩写")

        # ---- 5. 存档/读档往返 + 续局 ----
        run2 = eng.start(active_themes=["tentacle"], mix_policy="single_theme", floors=3, seed=7)
        eng.advance(run2, choice_id="step_in")
        saved = save_run(eng, run2, tmp / "saves", slot="autosave")
        check(Path(saved).is_file(), f"存档写出（{Path(saved).name}）")
        loaded = load_run(tmp / "saves", "dungeon", slot="autosave")
        check(loaded["event_id"] == run2["event_id"], "读档恢复当前事件")
        check(loaded["rng_state"] == run2["rng_state"], "RNG 状态读档往返一致")
        eng.advance(loaded, choice_id="still")
        check(loaded["event_id"] == "tentacle.enc.hold", f"读档后续局推进（实际 {loaded['event_id']}）")

        # ---- 6. 未知事件拒绝 ----
        try:
            eng.advance(run, choice_id="no_such_choice")
            check(False, "未知选项应被拒绝")
        except Exception:
            check(True, "未知选项被拒绝（fail-closed）")

        # ---- 7. 反馈查表 + 三态提示 ----
        fb = resolve_feedback(pack.event_index["tentacle.enc.wrap_arm"], pack.binding_index)
        check(len(fb["on_enter"]) >= 2, f"wrap_arm 反馈查表得到动作（{len(fb['on_enter'])} 条）")
        check(fb["hint"] in ("轻微", "持续", "已清理", "无"), f"三态提示 = {fb['hint']!r}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print(f"\n自检结果：{passed}/{total} 通过")
    if failures:
        print("失败项：", failures)
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
