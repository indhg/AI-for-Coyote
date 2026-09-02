# -*- coding: utf-8 -*-
"""测试模式模拟设备后端：不连郊狼，假装已配对，收命令只记录不真发。

AppState.set_test_mode(True) 会把活动后端换成 SimulatedBackend：
- ready() 恒 True、to_state() 报 paired → 前端解锁聊天/地牢/通道卡；
- apply / start_pulse_hold 只记日志并返回 False → 上层统一标「模拟」；
- 强度/波形跟踪仍走 SafetyManager.record，通道卡数值照常走动；
- 配合 safety.dry_run=True，所有动作都按 dry-run 语义记录，绝不触达真实设备。
"""
from __future__ import annotations

import logging
import uuid

from .base import STATUS_PAIRED, DeviceBackend

logger = logging.getLogger("ai-for-coyote.device.sim")


class SimulatedBackend(DeviceBackend):
    """测试模式：模拟一台已配对的郊狼（收命令不真发）。"""

    name = "sim"

    def __init__(self) -> None:
        super().__init__()
        self._cid = "SIM-" + uuid.uuid4().hex[:8].upper()
        self._loops = {"A": False, "B": False}

    # ---------- 生命周期 ----------
    async def start(self) -> None:
        logger.info("模拟设备就绪（测试模式 · 不发送真实命令）")

    async def stop(self) -> None:
        self._loops = {"A": False, "B": False}
        self._notify_disconnect({"reason": "test_mode_off"})

    # ---------- 命令（只记录，不真发） ----------
    async def apply(self, cmd: dict) -> bool:
        logger.info("模拟动作（不真发）: %s", cmd)
        return False

    async def start_pulse_hold(self, ch_name: str, cmd: dict) -> bool:
        if ch_name in self._loops:
            self._loops[ch_name] = True
        logger.info("模拟持续波形 %s「%s」（不真发）", ch_name, cmd.get("pattern"))
        return False

    def stop_pulse_hold(self, ch_name: str | None = None) -> None:
        if ch_name is None:
            self._loops = {"A": False, "B": False}
        elif ch_name in self._loops:
            self._loops[ch_name] = False

    def loops_active(self) -> dict:
        return dict(self._loops)

    # ---------- 状态 ----------
    def ready(self) -> bool:
        return True

    def controller_id(self) -> str | None:
        return self._cid

    def client_state(self) -> dict | None:
        return {
            "clientId": self._cid,
            "devices": [{"slotId": "SIM-SLOT", "name": "测试设备（模拟）", "type": "sim"}],
            "props": {},
            "slotState": {},
        }

    def to_state(self) -> dict:
        client = self.client_state()
        return {
            "status": STATUS_PAIRED,
            "controller_id": self._cid,
            "url": "",
            "clients": [client] if client else [],
            "last_error": "",
            "backend": self.name,
            "scanned": [],
        }
