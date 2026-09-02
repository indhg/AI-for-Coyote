# -*- coding: utf-8 -*-
"""M3 安全绑定自检：绑定动作 → SafetyManager 的校验/钳制/回归。

覆盖：正常执行、强度钳制、急停拒绝、断连清零、过热降上限、on_exit 清理、通道关闭拒绝。
运行：仓库根目录下 `python -m backend.dungeon.m3_selftest`
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from ..safety import SafetyManager
from .executor import FeedbackExecutor
from .loader import load_pack

SAMPLE = Path(__file__).resolve().parents[1] / "story_pack" / "sample"

_WAVES = ["呼吸", "潮汐", "挤压"]


def _cfg() -> dict:
    return {
        "safety": {
            "channels": {"A": {"max_strength": 200}, "B": {"max_strength": 200}},
            "max_temp_duration_s": 10,
            "max_strength_step": 40,
            "overheat_reduce_to": 20,
        },
        "playback": {"max_duration_s": 10, "min_duration_s": 3},
        "presets": {
            name: {
                "waveform": f"wave_{name}", "label": name,
                "frames": ["0A0A0A0A00000000"], "default_duration_s": 6.4,
                "max_duration_s": 30, "category": "经典波形",
            }
            for name in _WAVES
        },
        "ui": {},
        "app": {"dry_run": True},
        "device_channels": {
            "A": {"name": "贴片", "location": "小穴", "baseline": 15, "enabled": True},
            "B": {"name": "肛塞", "location": "后穴", "baseline": 5, "enabled": True},
        },
    }


def _new_safety() -> SafetyManager:
    return SafetyManager(_cfg())


def _binding(pack, key: str) -> dict:
    return pack.binding_index[key]


async def _main() -> int:
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

    pack = load_pack(SAMPLE)
    wrap = list(_binding(pack, "tentacle.fb.wrap_arm")["actions"])
    cleanup = list(_binding(pack, "tentacle.fb.wrap_arm").get("cleanup") or [])
    check(len(wrap) == 2, f"wrap_arm 绑定有 2 条动作（实际 {len(wrap)}）")
    check(len(cleanup) == 1, f"wrap_arm 有 cleanup（实际 {len(cleanup)} 条）")

    # 1. 正常执行
    s = _new_safety()
    ex = FeedbackExecutor(s, dry_run=True)
    r = await ex.execute(wrap)
    check(len(r["executed"]) == 2 and not r["dropped"],
          f"wrap_arm 反馈正常执行（executed={len(r['executed'])}, dropped={len(r['dropped'])}）")
    check(s.current["A"] == 15, f"hold 记录后 A 通道强度 = 15（实际 {s.current['A']}）")
    check(s.pulse_active()["A"] is True, "pulse_hold 记录后 A 通道波形播放中")

    # 2. 强度钳制（value 999 → 100）
    s2 = _new_safety()
    ex2 = FeedbackExecutor(s2, dry_run=True)
    r2 = await ex2.execute([{"op": "hold_strength", "channel": "A", "value": 999}])
    clamped = r2["executed"][0]["cmd"]["value"] if r2["executed"] else None
    check(clamped == 100, f"强度 999 被钳制到 100（实际 {clamped}）")

    # 3. 急停拒绝
    s3 = _new_safety()
    s3.estop()
    ex3 = FeedbackExecutor(s3, dry_run=True)
    r3 = await ex3.execute(wrap)
    check(len(r3["dropped"]) == 2 and not r3["executed"], "急停中反馈动作全部被拒")

    # 4. 断连清零
    s4 = _new_safety()
    ex4 = FeedbackExecutor(s4, dry_run=True)
    await ex4.execute(wrap)
    s4.record({"kind": "stop"})  # 模拟 on_client_disconnected
    check(s4.current == {"A": 0, "B": 0}, "断连清零后 A/B 强度归零")

    # 5. 过热降上限（50 → 20）
    s5 = _new_safety()
    s5.overheat["A"] = True
    ex5 = FeedbackExecutor(s5, dry_run=True)
    r5 = await ex5.execute([{"op": "hold_strength", "channel": "A", "value": 50}])
    clamped5 = r5["executed"][0]["cmd"]["value"] if r5["executed"] else None
    check(clamped5 == 20, f"过热时强度 50 被钳到 20（实际 {clamped5}）")

    # 6. on_exit 清理
    s6 = _new_safety()
    ex6 = FeedbackExecutor(s6, dry_run=True)
    await ex6.execute(wrap)
    await ex6.cleanup(cleanup)
    check(s6.current["A"] == 0, f"cleanup 后 A 通道归零（实际 {s6.current['A']}）")

    # 7. 通道关闭拒绝
    s7 = _new_safety()
    s7.set_channel_enabled("A", False)
    ex7 = FeedbackExecutor(s7, dry_run=True)
    r7 = await ex7.execute([{"op": "hold_strength", "channel": "A", "value": 15}])
    check(len(r7["dropped"]) == 1 and "关闭" in r7["dropped"][0]["reason"], "A 通道关闭时 A 动作被拒")

    print(f"\n自检结果：{passed}/{total} 通过")
    if failures:
        print("失败项：", failures)
    return 0 if passed == total else 1


def main() -> int:
    return asyncio.run(_main())


if __name__ == "__main__":
    raise SystemExit(main())
