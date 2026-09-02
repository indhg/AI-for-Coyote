# -*- coding: utf-8 -*-
"""郊狼 v2（脉冲主机 V2 / D-LAB ESTIM01）BLE 直连 adapter（T043 §B adapter 二 / §C 主项）。

形态：电脑直接用 bleak 连接 v2 主机（跳过手机 App 桥）。
- 强度：PWM_AB2 特性绝对强度写（0-2047，bit21-11=A / bit10-0=B），UI 0-200 由 v2_codec 映射。
- 波形：官方 100ms 窗口，每拍按 V3 帧折成 XYZ 写对应通道波形特性；pulse/pulse_hold 均为写环。
- 连接生命周期：扫描(name 前缀 D-LAB ESTIM) → 连 → 订 PWM_AB2 notify → 写 S=0 → ready；
  notify 超时视为断开 → 回调上层（自动清零）+ 指数退避重连。

待实测（真机勾掉后删本注释）：
- 完整 UUID 拼接与特性归属（swap_wave_chars 配置）
- 官方 App 圆环数值口径与 Z 档听感
- 是否要系统 BLE 配对弹窗（Windows/macOS）
- Win10 旧机 GATT 100Hz 写是否掉包
"""
from __future__ import annotations

import asyncio
import logging
import time

from ..safety import SafetyManager
from . import v2_codec as codec
from .base import (
    STATUS_CONNECTING,
    STATUS_DISCONNECTED,
    STATUS_PAIRED,
    STATUS_READY,
    STATUS_WAITING,
    DeviceBackend,
)

logger = logging.getLogger("ai-for-coyote.device.coyote2")

try:  # 延迟可用性标记：未安装 bleak 时后端照常构造，start 时报错提示
    import bleak  # noqa: F401

    _BLEAK_OK = True
except Exception:  # noqa: BLE001
    _BLEAK_OK = False

# notify 超时判定（秒）
NOTIFY_TIMEOUT_S = 3.0
# 重连退避（秒）
RECONNECT_BACKOFF = (1.0, 3.0, 5.0, 8.0, 12.0, 15.0)


class Coyote2BleBackend(DeviceBackend):
    name = "coyote2_ble"

    def __init__(self, cfg, safety: SafetyManager,
                 on_event=None, on_action=None) -> None:
        super().__init__()
        self.cfg = cfg
        self.safety = safety
        self.on_event = on_event
        self.on_action = on_action

        ble_cfg = (cfg.get("device") or {}).get("ble") or {}
        self.name_prefix = str(ble_cfg.get("device_name_prefix", "D-LAB ESTIM"))
        self.preferred_address = str(ble_cfg.get("preferred_address", "") or "")
        self.adapter = str(ble_cfg.get("adapter", "auto") or "auto")
        self.swap_wave_chars = bool(ble_cfg.get("swap_wave_chars", False))
        self.wave_xy = tuple(int(x) for x in (ble_cfg.get("wave_xy") or [1, 10]))[:2]
        # UUID 覆盖（留空=按官方文档自动拼）
        self.override_uuids = {
            "svc_pwm": str(ble_cfg.get("svc_pwm", "") or ""),
            "char_ab2": str(ble_cfg.get("char_ab2", "") or ""),
            "char_a": str(ble_cfg.get("char_a", "") or ""),
            "char_b": str(ble_cfg.get("char_b", "") or ""),
        }

        self.status = STATUS_DISCONNECTED
        self.last_error = ""
        self._client = None          # bleak BleakClient
        self._ab2_s = {"A": 0, "B": 0}   # 本地强度快照（S，0-2047）
        self._scanned: list[dict] = []
        self._connect_task: asyncio.Task | None = None
        self._notify_last = 0.0
        self._device_name = ""
        self._loop_events: dict[str, asyncio.Event] = {}
        self._loop_tasks: dict[str, asyncio.Task] = {}
        self._revert_tasks: dict[str, asyncio.Task] = {}

    # ---------- UUID ----------
    def _uuid(self, key: str, default_short: int) -> str:
        return self.override_uuids.get(key) or codec.svc_uuid(default_short)

    def _char_a(self) -> str:
        if self.swap_wave_chars:
            return self._uuid("char_b", codec.CHAR_PWM_B34_SHORT)
        return self._uuid("char_a", codec.CHAR_PWM_A34_SHORT)

    def _char_b(self) -> str:
        if self.swap_wave_chars:
            return self._uuid("char_a", codec.CHAR_PWM_A34_SHORT)
        return self._uuid("char_b", codec.CHAR_PWM_B34_SHORT)

    # ---------- 生命周期 ----------
    async def start(self) -> None:
        if self._connect_task is None or self._connect_task.done():
            self._connect_task = asyncio.create_task(self._connect_loop())
            logger.info("coyote2 BLE 后端启动（前缀 %s，swap_wave=%s）",
                        self.name_prefix, self.swap_wave_chars)

    async def stop(self) -> None:
        self.stop_pulse_hold(None)
        self._cancel_revert(None)
        if self._connect_task:
            self._connect_task.cancel()
            self._connect_task = None
        await self._disconnect()

    async def _disconnect(self) -> None:
        client = self._client
        self._client = None
        if client is not None:
            try:
                await client.disconnect()
            except Exception:  # noqa: BLE001
                pass

    async def _connect_loop(self) -> None:
        """扫描 → 连接 → ready；断开/失败后指数退避重连。"""
        backoff_i = 0
        while True:
            try:
                if not _BLEAK_OK:
                    self.last_error = (
                        "未安装 bleak：请在终端执行 pip install bleak（郊狼 v2 BLE 直连需要）"
                    )
                    self.status = STATUS_DISCONNECTED
                    await asyncio.sleep(10)
                    continue
                await self._connect_once()
                backoff_i = 0
                if self.status == STATUS_READY:
                    await self._watch_connected()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                logger.warning("coyote2 BLE 异常: %s", exc)
                self.last_error = str(exc)[:200]
                self.status = STATUS_DISCONNECTED
            delay = RECONNECT_BACKOFF[min(backoff_i, len(RECONNECT_BACKOFF) - 1)]
            backoff_i += 1
            await asyncio.sleep(delay)

    async def _connect_once(self) -> None:
        from bleak import BleakClient, BleakScanner  # 延迟 import

        self.status = STATUS_CONNECTING
        # 1) 扫描
        devices = []
        try:
            found = await BleakScanner.discover(timeout=4.0)
            devices = [
                {"id": d.address, "name": d.name or "", "rssi": getattr(d, "rssi", None)}
                for d in found if (d.name or "").startswith(self.name_prefix)
            ]
        except Exception as exc:  # noqa: BLE001
            logger.warning("coyote2 扫描失败: %s", exc)
            self.last_error = f"BLE 扫描失败: {exc}"
            self.status = STATUS_WAITING
            return
        self._scanned = devices
        if not devices:
            self.status = STATUS_WAITING
            self.last_error = f"未发现 {self.name_prefix}* 设备（请确认设备开机且在配对范围）"
            return
        address = None
        if self.preferred_address:
            for d in devices:
                if d["id"] == self.preferred_address:
                    address = d["id"]
                    break
        if address is None:
            address = devices[0]["id"]
        self._device_name = next((d["name"] for d in devices if d["id"] == address), "D-LAB ESTIM01")

        # 2) 连接 + 订阅
        client = BleakClient(address, timeout=10.0)
        try:
            await client.connect()
        except Exception as exc:  # noqa: BLE001
            logger.warning("coyote2 连接失败 %s: %s", address, exc)
            self.last_error = f"连接失败: {exc}"
            self.status = STATUS_WAITING
            return
        self._client = client
        self.status = STATUS_PAIRED
        ab2_char = self._uuid("char_ab2", codec.CHAR_PWM_AB2_SHORT)

        async def on_notify(_char, data):
            try:
                a_s, b_s = codec.unpack_ab2(bytes(data))
                self._ab2_s["A"], self._ab2_s["B"] = a_s, b_s
                self._notify_last = time.monotonic()
                # 校准 safety 的本地强度（波形播放期由 pulse_until 自动忽略振幅）
                self.safety.update_device_state(
                    {
                        "intensityA": codec.s_to_ui(a_s),
                        "intensityB": codec.s_to_ui(b_s),
                    },
                    None,
                )
            except Exception:  # noqa: BLE001
                pass

        try:
            await client.start_notify(ab2_char, on_notify)
        except Exception as exc:  # noqa: BLE001
            logger.warning("coyote2 订阅 PWM_AB2 notify 失败: %s", exc)
            self.last_error = f"订阅失败: {exc}"
        # 3) 写 S=0 起步 + 标记 ready
        await self._write_ab2()
        self._notify_last = time.monotonic()
        self.status = STATUS_READY
        self.last_error = ""
        logger.info("coyote2 BLE 已连接: %s（%s）", self._device_name, address)
        if self.on_event:
            try:
                await self.on_event("ble_connected", {"name": self._device_name})
            except Exception:  # noqa: BLE001
                pass

    async def _watch_connected(self) -> None:
        """保活监视：notify 超时视为断。"""
        while self._client is not None:
            await asyncio.sleep(1.0)
            if self.status != STATUS_READY:
                break
            if time.monotonic() - self._notify_last > NOTIFY_TIMEOUT_S:
                logger.warning("coyote2 notify 超时 %ss，判定断开", NOTIFY_TIMEOUT_S)
                self.last_error = "设备 notify 超时（疑似断开/休眠）"
                await self._on_gone()
                break

    async def _on_gone(self) -> None:
        was_ready = self.status in (STATUS_READY, STATUS_PAIRED)
        self.stop_pulse_hold(None)
        self._cancel_revert(None)
        await self._disconnect()
        self.status = STATUS_DISCONNECTED
        self._ab2_s = {"A": 0, "B": 0}
        if was_ready:
            self._notify_disconnect({"reason": "ble_gone"})

    # ---------- 写入原语 ----------
    async def _write_ab2(self) -> bool:
        client = self._client
        if client is None:
            return False
        try:
            data = codec.pack_ab2(self._ab2_s["A"], self._ab2_s["B"])
            await client.write_gatt_char(
                self._uuid("char_ab2", codec.CHAR_PWM_AB2_SHORT), data, response=False
            )
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("coyote2 写强度失败: %s", exc)
            self.last_error = f"写强度失败: {exc}"
            return False

    async def _write_xyz(self, ch_name: str, xyz) -> bool:
        client = self._client
        if client is None:
            return False
        char = self._char_a() if ch_name == "A" else self._char_b()
        try:
            await client.write_gatt_char(char, codec.pack_xyz(*xyz), response=False)
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("coyote2 写波形失败(%s): %s", ch_name, exc)
            self.last_error = f"写波形失败: {exc}"
            return False

    async def _set_strength(self, ch_name: str | None, ui_value: int | None = None) -> bool:
        """写强度：ch_name=None 双通道；ui_value=None 表示归零（S=0）。"""
        if ui_value is None:
            target_s = 0
        else:
            target_s = codec.ui_to_s(ui_value)
        if ch_name is None:
            self._ab2_s = {"A": target_s, "B": target_s}
        else:
            self._ab2_s[ch_name] = target_s
        return await self._write_ab2()

    # ---------- 一次性命令 ----------
    async def apply(self, cmd: dict) -> bool:
        if self.status != STATUS_READY:
            return False
        kind = cmd.get("kind")
        ch_name = cmd.get("channel")
        try:
            if kind == "hold":
                return await self._set_strength(ch_name, int(cmd["value"]))
            if kind == "temp":
                ok = await self._set_strength(ch_name, int(cmd["value"]))
                if ok:
                    self._schedule_temp_revert(ch_name, float(cmd["duration_s"]))
                return ok
            if kind == "add":
                current_ui = codec.s_to_ui(self._ab2_s.get(ch_name, 0))
                return await self._set_strength(ch_name, max(0, current_ui + int(cmd["delta"])))
            if kind == "pulse":
                await self._start_wave(ch_name, cmd["frames"], float(cmd["duration_s"]))
                return True
            if kind == "clear":
                self._cancel_revert(ch_name)
                self.stop_pulse_hold(ch_name)
                if ch_name is None:
                    return await self._set_strength(None, 0)
                return await self._set_strength(ch_name, 0)
            if kind == "stop":
                self._cancel_revert(None)
                self.stop_pulse_hold(None)
                return await self._set_strength(None, 0)
        except Exception as exc:  # noqa: BLE001
            logger.warning("coyote2 apply(%s) 异常: %s", kind, exc)
            self.last_error = f"apply {kind} 异常: {exc}"
            return False
        return False

    # ---------- 波形写环 ----------
    async def start_pulse_hold(self, ch_name: str, cmd: dict) -> bool:
        if self.status != STATUS_READY:
            return False
        await self._start_wave(ch_name, cmd["frames"], None)
        return True

    def stop_pulse_hold(self, ch_name: str | None = None) -> None:
        names = [ch_name] if ch_name else list(self._loop_events)
        for name in names:
            event = self._loop_events.pop(name, None)
            if event:
                event.set()
            task = self._loop_tasks.pop(name, None)
            if task:
                task.cancel()
        if ch_name and ch_name in self.safety.pulse_until:
            self.safety.pulse_until[ch_name] = 0.0

    def loops_active(self) -> dict:
        return {ch: ch in self._loop_tasks for ch in ("A", "B")}

    async def _start_wave(self, ch_name: str, frames: list, duration_s: float | None) -> None:
        """100ms 写环：逐帧 XYZ 写入；duration_s=None 无限直到 stop。"""
        if ch_name not in ("A", "B"):
            return
        self.stop_pulse_hold(ch_name)
        stop_event = asyncio.Event()
        self._loop_events[ch_name] = stop_event
        x0, y0 = self.wave_xy[0], self.wave_xy[1]
        xyzs = [codec.v3_frame_to_xyz(f, ch_name, x0, y0) for f in (frames or [])]
        if not xyzs:
            xyzs = [codec.wave_zero_xyz()]
        tick = codec.FRAME_MS / 1000.0

        async def worker() -> None:
            started = time.monotonic()
            while not stop_event.is_set():
                for idx, xyz in enumerate(xyzs):
                    if stop_event.is_set() or self.safety.estop_active:
                        return
                    await self._write_xyz(ch_name, xyz)
                    target = started + (idx + 1) * tick
                    wait = target - time.monotonic()
                    if wait > 0:
                        try:
                            await asyncio.wait_for(stop_event.wait(), timeout=wait)
                            return
                        except asyncio.TimeoutError:
                            pass
                if duration_s is not None and time.monotonic() - started >= duration_s:
                    break
            # 结束：停脉冲
            await self._write_xyz(ch_name, codec.wave_zero_xyz())
            self._loop_tasks.pop(ch_name, None)
            self._loop_events.pop(ch_name, None)

        self._loop_tasks[ch_name] = asyncio.create_task(worker())

    # ---------- temp 归零 ----------
    def _cancel_revert(self, ch_name: str | None) -> None:
        names = [ch_name] if ch_name else list(self._revert_tasks)
        for name in names:
            task = self._revert_tasks.pop(name, None)
            if task:
                task.cancel()

    def _schedule_temp_revert(self, ch_name: str, duration_s: float) -> None:
        async def revert() -> None:
            try:
                await asyncio.sleep(duration_s)
            except asyncio.CancelledError:
                return
            if self.safety.estop_active:
                return
            await self._set_strength(ch_name, 0)
            self.safety.record({"kind": "zero", "channel": ch_name})
            logger.info("coyote2 爆发结束，%s 通道归零", ch_name)

        self._cancel_revert(ch_name)
        self._revert_tasks[ch_name] = asyncio.create_task(revert())

    # ---------- 状态 ----------
    def ready(self) -> bool:
        return self.status == STATUS_READY

    def client_state(self) -> dict | None:
        if self.status != STATUS_READY:
            return None
        return {
            "clientId": "ble",
            "slotId": "ble",
            "devices": [{"slotId": "ble", "name": self._device_name or "D-LAB ESTIM01", "type": "v2"}],
            "props": {
                "slotId": "ble",
                "intensityA": codec.s_to_ui(self._ab2_s["A"]),
                "intensityB": codec.s_to_ui(self._ab2_s["B"]),
            },
            "slotState": {},
        }

    def to_state(self) -> dict:
        clients = []
        if self.status == STATUS_READY:
            clients = [self.client_state()]
        return {
            "status": self.status,
            "controller_id": None,
            "url": "",
            "clients": clients,
            "last_error": self.last_error,
            "backend": self.name,
            "scanned": list(self._scanned),
            "device_name": self._device_name,
            "swap_wave_chars": self.swap_wave_chars,
        }
