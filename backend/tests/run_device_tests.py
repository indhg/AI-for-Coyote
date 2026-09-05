# -*- coding: utf-8 -*-
"""设备后端抽象层回归测试（T043 阶段①验收）：python backend/tests/run_device_tests.py

覆盖：
- v2_codec：UI↔S 映射、AB2/XYZ 位域打包解包往返、V3 帧→XYZ 折取
- DGLabRelayBackend._build_frames：hold/add/clear/stop/pulse 帧结构与现网一致
- GameLoop 全链路（dry：safety → backend.apply → 假中继帧）与急停/断开
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.device import v2_codec as codec  # noqa: E402
from backend.device.dglab_relay import DGLabRelayBackend  # noqa: E402
from backend.game_loop import GameLoop  # noqa: E402
from backend.safety import SafetyManager  # noqa: E402

RESULTS: list[tuple[str, bool]] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond)))
    print(("PASS  " if cond else "FAIL  ") + name + (f"  |  {detail}" if detail else ""))


def mini_cfg() -> dict:
    return {
        "app": {"dry_run": False},
        "relay": {"url": "ws://127.0.0.1:9998", "reconnect_delay_s": 3,
                  "lan_ip": "auto", "public_url": ""},
        "safety": {
            "channels": {"A": {"max_strength": 200}, "B": {"max_strength": 200}},
            "max_temp_duration_s": 10,
            "max_strength_step": 40,
            "auto_clear_on_disconnect": True,
            "overheat_reduce_to": 20,
        },
        "playback": {"frame_ms": 100, "min_duration_s": 3, "max_duration_s": 10,
                     "loop_batch_s": 30, "loop_overlap_s": 0.3},
        "presets": {
            "呼吸": {"waveform": "breath", "label": "呼吸", "default_duration_s": 5,
                     "max_duration_s": 30,
                     "frames": ["0A0A0A0A00000000", "0B0B0B0B00000000", "0C0C0C0C00000000"]},
        },
        "ui": {"default_wave": "呼吸", "quick_strengths": [20],
               "baseline_strength": {"A": 15, "B": 5}},
        "device_channels": {
            "A": {"name": "贴片", "location": "小穴", "baseline": 15},
            "B": {"name": "肛塞", "location": "后穴", "baseline": 5},
        },
        "log": {"history_keep": 40},
        "autopilot": {"enabled": False, "interval_s": 12},
        "camera": {"enabled": False, "auto_observe": True, "observe_interval_s": 10},
        "character": {"rage_baseline": 0, "role": "测试", "role_title": "主人",
                      "roles": ["测试"], "profile": "测", "profiles": ["测"],
                      "profile_available": {}, "profile_level": "中",
                      "player_nick": "小柳", "name": "测试"},
    }


class FakeRelay:
    """假中继：记录帧、恒 paired。"""

    def __init__(self) -> None:
        self.frames: list[dict] = []
        self.client_id = "c1"
        self.slot_id = "s1"
        self.controller_id = "ctl-1"

    def first_client_id(self):
        return self.client_id

    def get_slot_id(self):
        return self.slot_id

    async def send_frame(self, frame: dict) -> bool:
        self.frames.append(frame)
        return True

    def to_state(self) -> dict:
        return {"status": "paired", "controller_id": self.controller_id,
                "url": "ws://fake", "clients": [], "last_error": ""}


def _frame_op(frame: dict) -> dict | None:
    data = (frame.get("data") or {}).get("data") or {}
    return data if isinstance(data, dict) else None


def test_codec() -> None:
    check("ui_to_s: 0->0 / 100->1024 附近 / 200->2047 钳制",
          codec.ui_to_s(0) == 0 and codec.ui_to_s(200) == 2047
          and codec.ui_to_s(9999) == 2047 and abs(codec.ui_to_s(100) - 1024) <= 1)
    check("s_to_ui 往返", abs(codec.s_to_ui(codec.ui_to_s(150)) - 150) <= 1)
    # 位域：A=2047(bit21-11), B=1(bit10-0) -> bytes
    data = codec.pack_ab2(2047, 1)
    a_s, b_s = codec.unpack_ab2(data)
    check("pack/unpack_ab2 往返", a_s == 2047 and b_s == 1)
    check("AB2 位域：A=1 → bit11 → 0x0800",
          codec.pack_ab2(1, 0) == (1 << 11).to_bytes(3, "big"))
    check("AB2 位域：B=1 → bit0",
          codec.pack_ab2(0, 1) == (1).to_bytes(3, "big"))
    xyz = codec.pack_xyz(1, 10, 5)
    x, y, z = codec.unpack_xyz(xyz)
    check("pack/unpack_xyz 往返", (x, y, z) == (1, 10, 5))
    x0, y0, z0 = codec.v3_frame_to_xyz("0A0A0A0A00000000", "A")  # A=4×10
    check("V3 A 帧 -> Z=round(10/5)=2", z0 == 2 and x0 == 1 and y0 == 10)
    x1, y1, z1 = codec.v3_frame_to_xyz("0A0A0A0A00000000", "B")  # B 半段全 0
    check("V3 B 半段 -> Z=0", z1 == 0)
    check("非法 hex 兜底", codec.v3_frame_to_xyz("zz", "A")[2] == 0)


def test_dglab_frames() -> None:
    cfg = mini_cfg()
    safety = SafetyManager(cfg)
    backend = DGLabRelayBackend(cfg, safety)
    backend.relay = FakeRelay()  # 换假中继
    cid, sid = "c1", "s1"

    def frames_for(cmd):
        return backend._build_frames(cmd, cid, sid)

    f = frames_for({"kind": "hold", "channel": "A", "value": 50})
    op = _frame_op(f[0])
    check("hold: add_strength delta=50", len(f) == 1 and op and op.get("t") == 3
          and op.get("v") == 50, detail=str(f))

    safety.record({"kind": "hold", "channel": "A", "value": 30})
    f = frames_for({"kind": "clear", "channel": "A"})
    ops = [_frame_op(x) for x in f]
    check("clear A: clear + add(-30) + reset(3 帧)",
          len(f) == 3 and ops[0].get("s") == sid and ops[1].get("v") == -30
          and ops[2].get("t") == 7, detail=str(f))

    safety.record({"kind": "stop"})
    f = frames_for({"kind": "stop"})
    check("stop: clear 全 + A/B 双 reset", len(f) == 3, detail=str(len(f)))

    f = frames_for({"kind": "pulse", "channel": "A", "frames": ["0A0A0A0A00000000"],
                    "duration_s": 1.0})
    op = _frame_op(f[0])
    check("pulse: tiled 10 帧", len(f) == 1 and op and op.get("t") == 0
          and len(op.get("v", [])) == 10, detail=str(len(op.get("v", [])) if op else -1))

    f = frames_for({"kind": "temp", "channel": "A", "value": 60, "duration_s": 1.0})
    op = _frame_op(f[0])
    check("temp: delta 帧（t=3, v=60）", len(f) == 1 and op and op.get("t") == 3
          and op.get("v") == 60, detail=str(f))
    backend._cancel_revert("A")
    backend.stop_pulse_hold(None)


async def test_game_loop_chain() -> None:
    cfg = mini_cfg()
    safety = SafetyManager(cfg)
    fake = FakeRelay()
    backend = DGLabRelayBackend(cfg, safety)
    backend.relay = fake
    loop = GameLoop(cfg, None, safety, backend)

    executed, dropped = await loop.execute_actions(
        [{"op": "hold_strength", "channel": "A", "value": 50}]
    )
    check("链: hold 执行且 sent",
          len(executed) == 1 and executed[0]["sent"] and not dropped,
          detail=str([e["label"] for e in executed]))
    check("链: 假中继收到 add 帧", len(fake.frames) >= 1)

    executed, dropped = await loop.execute_actions(
        [{"op": "pulse_hold", "channel": "B", "pattern": "呼吸"}]
    )
    check("链: pulse_hold 启动循环",
          len(executed) == 1 and executed[0]["sent"]
          and backend.loops_active().get("B") is True)
    await asyncio.sleep(0.05)
    backend.stop_pulse_hold("B")
    check("链: stop_pulse_hold 后循环停",
          not backend.loops_active().get("B"))

    # temp 归零任务登记（apply 路径）
    fake.frames.clear()
    backend._cancel_revert(None)
    executed, dropped = await loop.execute_actions(
        [{"op": "temp_strength", "channel": "A", "value": 60, "duration_s": 5}]
    )
    check("链: temp 经 apply 登记归零任务",
          len(executed) == 1 and executed[0]["sent"]
          and "A" in backend.revert_tasks and not dropped)
    backend._cancel_revert("A")

    # 急停
    res = await loop.estop()
    check("链: estop 清零发出", res["sent"] and safety.estop_active
          and safety.current == {"A": 0, "B": 0})

    # 断开清零
    await loop.resume()
    fake.frames.clear()
    loop.on_client_disconnected()
    check("链: on_client_disconnected 停循环/清 patterns",
          loop.patterns == {"A": None, "B": None}
          and not any(backend.loops_active().values()))

    # 地牢 FeedbackExecutor 走同一链路（send 注入 backend.apply）——dungeon_v2 版（旧 backend.dungeon 已归档 2026-09-04）
    from backend.dungeon_v2.feedback import FeedbackExecutor
    ex = FeedbackExecutor(cfg, safety)
    ex.send = backend.apply
    executed, dropped = await ex.run([{"op": "hold_strength", "channel": "B", "value": 20}])
    check("链: 地牢反馈经 backend 真发", executed and executed[0]["sent"],
          detail=str([e["label"] for e in executed]))


async def test_estop_blocks_while_active() -> None:
    cfg = mini_cfg()
    safety = SafetyManager(cfg)
    backend = DGLabRelayBackend(cfg, safety)
    backend.relay = FakeRelay()
    loop = GameLoop(cfg, None, safety, backend)
    await loop.estop()
    _, dropped = await loop.execute_actions(
        [{"op": "hold_strength", "channel": "A", "value": 50}]
    )
    check("急停中拒绝一切动作", len(dropped) == 1)


def main() -> int:
    test_codec()
    test_dglab_frames()
    asyncio.run(test_game_loop_chain())
    asyncio.run(test_estop_blocks_while_active())
    fails = [name for name, ok in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(fails)}/{len(RESULTS)} passed")
    if fails:
        print("FAILED:", ", ".join(fails))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
