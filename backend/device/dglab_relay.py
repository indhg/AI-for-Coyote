# -*- coding: utf-8 -*-
"""现网 dglab-websocket-server v4 桥 adapter（T043 §B adapter 一）。

行为 = 改造前 game_loop.py 的发送/循环/归零逻辑 + RelayClient，零行为变化：
- 一次性命令（temp/hold/add/pulse/clear/stop）→ V4 RPC 帧发送；
- pulse_hold 循环波形 → 本机分批重发（不依赖 App 的 d=0，实测不可靠）；
- temp 归零定时器登记在本 adapter（stop()/clear/estop 路径可取消）。
"""
from __future__ import annotations

import asyncio
import logging

from ..device_ops import CHANNEL, DeviceOps
from ..relay_client import RelayClient
from ..safety import SafetyManager
from .base import (
    STATUS_CONNECTING,
    STATUS_DISCONNECTED,
    STATUS_PAIRED,
    STATUS_READY,
    STATUS_WAITING,
    DeviceBackend,
)

logger = logging.getLogger("ai-for-coyote.device.dglab")


class DGLabRelayBackend(DeviceBackend):
    """dglab-websocket-server v4 桥。持有 RelayClient 并转发其中继事件。"""

    name = "dglab_relay"

    def __init__(self, cfg, safety: SafetyManager,
                 on_event=None, on_action=None) -> None:
        super().__init__()
        self.cfg = cfg
        self.safety = safety
        self.on_event = on_event      # async (event, payload)，原样转发中继事件
        self.on_action = on_action    # async (action, client_id)

        self.relay = RelayClient(
            str(cfg["relay"]["url"]),
            reconnect_delay_s=float(cfg["relay"].get("reconnect_delay_s", 3)),
            on_event=self._forward_event,
            on_action=self.on_action,
        )
        self.ops = DeviceOps()

        self._relay_task: asyncio.Task | None = None
        # 循环波形：channel -> (task, stop_event)
        self.loop_tasks: dict[str, asyncio.Task] = {}
        self.loop_events: dict[str, asyncio.Event] = {}
        # temp 归零任务：channel -> task
        self.revert_tasks: dict[str, asyncio.Task] = {}

    # ---------- 事件转发（附断开通知） ----------
    async def _forward_event(self, event: str, payload: dict) -> None:
        if event == "disconnected":
            self._notify_disconnect(payload)
        if self.on_event:
            await self.on_event(event, payload)

    # ---------- 生命周期 ----------
    async def start(self) -> None:
        if self._relay_task is None or self._relay_task.done():
            self._relay_task = asyncio.create_task(self.relay.run())
            logger.info("dglab 中继后端启动：%s", self.relay.url)

    async def stop(self) -> None:
        self.stop_pulse_hold(None)
        self._cancel_revert(None)
        if self._relay_task:
            self._relay_task.cancel()
            self._relay_task = None

    # ---------- 一次性命令 ----------
    async def apply(self, cmd: dict) -> bool:
        client_id = self.relay.first_client_id()
        slot_id = self.relay.get_slot_id()
        if client_id is None or slot_id is None:
            return False
        kind = cmd.get("kind")
        if kind == "temp":
            self._cancel_revert(cmd.get("channel"))
        frames = self._build_frames(cmd, client_id, slot_id)
        if kind == "temp":
            self._schedule_temp_revert(client_id, slot_id, cmd)
        if not frames:
            return True
        return all(await self._send_all(frames))

    async def _send_all(self, frames: list[dict]) -> list[bool]:
        return [await self.relay.send_frame(f) for f in frames]

    def _build_frames(self, cmd: dict, client_id: str | None, slot_id: str | None) -> list[dict]:
        """内部命令 -> V4 服务器帧列表（复刻原 game_loop 逻辑）。"""
        frames: list[dict] = []
        kind = cmd["kind"]
        if client_id is None or slot_id is None:
            return frames
        ch = CHANNEL.get(cmd.get("channel"))
        ch_name = cmd.get("channel")
        if kind == "temp":
            # 爆发：加差值到目标，到时自动归零（归零由 _schedule_temp_revert 负责）
            delta = cmd["value"] - self.safety.current[ch_name]
            if delta:
                frames.append(self.ops.add_strength(client_id, slot_id, ch, delta))
        elif kind == "hold":
            # 持续强度：加差值到目标（AddIntensity 是实测可靠的原语）
            delta = cmd["value"] - self.safety.current[ch_name]
            if delta:
                frames.append(self.ops.add_strength(client_id, slot_id, ch, delta))
        elif kind == "add":
            frames.append(self.ops.add_strength(client_id, slot_id, ch, cmd["delta"]))
        elif kind == "pulse":
            # 波形按帧消费（每帧 100ms），帧播完即停；tiling 补齐到请求的时长
            base = cmd["frames"]
            total = max(1, int(round(cmd["duration_s"] * 10)))
            tiled = (base * (total // len(base) + 1))[:total] if base else []
            frames.append(
                self.ops.pulse(
                    client_id, slot_id, ch, tiled,
                    int(cmd["duration_s"] * 1000), immediate=True,
                )
            )
        elif kind == "clear":
            frames.append(
                self.ops.clear(client_id, slot_id, None if cmd["channel"] is None else ch)
            )
            # 用可靠的 AddIntensity 负值归零，另发 reset 兜底
            if cmd["channel"] is None:
                for c in ("A", "B"):
                    if self.safety.current[c]:
                        frames.append(
                            self.ops.add_strength(
                                client_id, slot_id, CHANNEL[c], -self.safety.current[c]
                            )
                        )
                    frames.append(self.ops.reset_intensity(client_id, slot_id, CHANNEL[c]))
            else:
                if self.safety.current[ch_name]:
                    frames.append(
                        self.ops.add_strength(
                            client_id, slot_id, ch, -self.safety.current[ch_name]
                        )
                    )
                frames.append(self.ops.reset_intensity(client_id, slot_id, ch))
        elif kind == "stop":
            frames.append(self.ops.clear(client_id, slot_id))
            for c in ("A", "B"):
                if self.safety.current[c]:
                    frames.append(
                        self.ops.add_strength(
                            client_id, slot_id, CHANNEL[c], -self.safety.current[c]
                        )
                    )
                frames.append(self.ops.reset_intensity(client_id, slot_id, CHANNEL[c]))
        return frames

    # ---------- temp 归零 ----------
    def _cancel_revert(self, ch_name: str | None) -> None:
        names = [ch_name] if ch_name else list(self.revert_tasks)
        for name in names:
            task = self.revert_tasks.pop(name, None)
            if task:
                task.cancel()

    def _schedule_temp_revert(
        self, client_id: str, slot_id: str, cmd: dict
    ) -> None:
        """爆发时长结束后自动归零（AddIntensity 负值 + reset 兜底）。"""
        ch = CHANNEL.get(cmd["channel"])
        ch_name = cmd["channel"]
        duration_s = float(cmd["duration_s"])

        async def revert() -> None:
            try:
                await asyncio.sleep(duration_s)
            except asyncio.CancelledError:
                return
            if self.safety.estop_active:
                return
            value = self.safety.current[ch_name]
            frames = []
            if value:
                frames.append(self.ops.add_strength(client_id, slot_id, ch, -value))
            frames.append(self.ops.reset_intensity(client_id, slot_id, ch))
            sent = all(await self._send_all(frames))
            if sent:
                self.safety.record({"kind": "zero", "channel": ch_name})
                logger.info("爆发结束，%s 通道自动归零", ch_name)

        self.revert_tasks[ch_name] = asyncio.create_task(revert())

    # ---------- 循环波形 ----------
    async def start_pulse_hold(self, ch_name: str, cmd: dict) -> bool:
        client_id = self.relay.first_client_id()
        slot_id = self.relay.get_slot_id()
        if client_id is None or slot_id is None:
            return False
        self.stop_pulse_hold(ch_name)
        ch = CHANNEL.get(ch_name)
        base = cmd["frames"]
        playback = self.cfg["playback"]
        frame_s = float(playback["frame_ms"]) / 1000.0
        natural = max(len(base) * frame_s, 0.1)
        batch_s = max(float(playback["loop_batch_s"]), natural)
        mult = max(1, round(batch_s / natural))
        batch_s = natural * mult
        overlap = min(float(playback["loop_overlap_s"]), batch_s * 0.5)
        total = max(1, int(round(batch_s * 10)))
        tiled = (base * (total // len(base) + 1))[:total] if base else []
        frame = self.ops.pulse(
            client_id, slot_id, ch, tiled, int(batch_s * 1000), immediate=True
        )
        wait_s = max(0.1, batch_s - overlap)

        stop_event = asyncio.Event()
        self.loop_events[ch_name] = stop_event

        async def worker() -> None:
            ok = await self._send_all([frame])
            if not ok:
                return
            logger.info(
                "%s 通道循环波形开始：%s（批次 %.1fs，提前 %.2fs 覆盖）",
                ch_name, cmd["pattern"], batch_s, overlap,
            )
            while not stop_event.is_set():
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=wait_s)
                    break
                except asyncio.TimeoutError:
                    pass
                if self.safety.estop_active:
                    break
                await self._send_all([frame])
            logger.info("%s 通道循环波形结束：%s", ch_name, cmd["pattern"])

        self.loop_tasks[ch_name] = asyncio.create_task(worker())
        return True

    def stop_pulse_hold(self, ch_name: str | None = None) -> None:
        names = [ch_name] if ch_name else list(self.loop_events)
        for name in names:
            event = self.loop_events.pop(name, None)
            if event:
                event.set()
            task = self.loop_tasks.pop(name, None)
            if task:
                task.cancel()
        if ch_name and ch_name in self.safety.pulse_until:
            self.safety.pulse_until[ch_name] = 0.0

    def loops_active(self) -> dict:
        return {ch: ch in self.loop_tasks for ch in ("A", "B")}

    # ---------- 状态 ----------
    def ready(self) -> bool:
        return bool(self.relay.first_client_id() and self.relay.get_slot_id())

    def controller_id(self) -> str | None:
        return self.relay.controller_id

    def client_state(self) -> dict | None:
        cid = self.relay.first_client_id()
        return self.relay.clients.get(cid or "") if cid else None

    def _map_status(self, s: str) -> str:
        # 现网 relay 状态对齐 DeviceBackend 语义；paired ≈ 可发
        if s == "paired":
            return STATUS_PAIRED
        if s in ("waiting",):
            return STATUS_WAITING
        if s == "connecting":
            return STATUS_CONNECTING
        return STATUS_DISCONNECTED

    def to_state(self) -> dict:
        st = self.relay.to_state()
        st["status"] = self._map_status(st.get("status", STATUS_DISCONNECTED))
        st["backend"] = self.name
        st["scanned"] = []
        # ready 语义：dglab 下 paired 即视为可发（前端仍读 status/controller_id）
        if st["status"] == STATUS_PAIRED:
            st["status"] = STATUS_PAIRED
        return st
