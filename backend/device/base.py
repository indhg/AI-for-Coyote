# -*- coding: utf-8 -*-
"""DeviceBackend 抽象接口（T043 §B）。

安全不变量（任何 backend 不得违反）：
- 所有命令先经 SafetyManager.validate 得到内部 cmd，才交给 backend.apply；
- backend 不得自抬上限、不得跳过步长/时长钳制；
- 断开/急停路径必须把强度写 0（是否自动清零由上层按 auto_clear_on_disconnect 决定）；
- backend 可以持有 safety 引用只用于「读当前强度做差值/校准」与「record 归零等执行记录」。
"""
from __future__ import annotations

import abc
import asyncio

# A/B 通道（字母 -> V4 数字通道；BLE 也沿用字母语义）
CHANNEL = {"A": 0, "B": 1}
CHANNEL_NAME = {0: "A", 1: "B"}

# 连接状态（对齐现网 relay 语义；BLE 用 ready 表示已连上、可下发）
STATUS_DISCONNECTED = "disconnected"
STATUS_CONNECTING = "connecting"
STATUS_WAITING = "waiting"      # dglab：等 App 扫码接入；BLE：扫描中/未发现
STATUS_PAIRED = "paired"        # dglab：App 已接入
STATUS_READY = "ready"          # BLE：GATT 通、notify 已订、强度已写 0


class DeviceBackend(abc.ABC):
    """设备后端接口。

    apply 接收的是 safety.validate 产出的内部 cmd（kind: temp/hold/add/pulse/clear/stop）；
    pulse_hold 属循环类，由 start_pulse_hold / stop_pulse_hold 单独处理（backend 内维护定时任务）。
    """

    name = "base"

    def __init__(self) -> None:
        self._disconnect_cbs: list = []

    # ---------- 生命周期 ----------
    @abc.abstractmethod
    async def start(self) -> None:
        """启动连接（常驻任务：自动重连/扫描）。"""

    @abc.abstractmethod
    async def stop(self) -> None:
        """关闭连接并取消所有内部任务（循环波形 / temp 归零）。"""

    # ---------- 命令 ----------
    @abc.abstractmethod
    async def apply(self, cmd: dict) -> bool:
        """执行一条已校验的一次性内部 cmd；返回是否真正送达设备。

        dry_run 由调用方（GameLoop/FeedbackExecutor）短路，不进 backend。
        """

    @abc.abstractmethod
    async def start_pulse_hold(self, ch_name: str, cmd: dict) -> bool:
        """启动某通道的循环波形（cmd.kind == pulse_hold）。返回是否已启动。"""

    @abc.abstractmethod
    def stop_pulse_hold(self, ch_name: str | None = None) -> None:
        """停掉通道循环波形；ch_name=None 停全部。"""

    # ---------- 状态 ----------
    def loops_active(self) -> dict:
        """{通道: 是否循环波形中}（页面/保底规则用）。"""
        return {"A": False, "B": False}

    def ready(self) -> bool:
        """当前是否可下发命令（dglab：App 已接且有 slot；BLE：status==ready）。"""
        return False

    def controller_id(self) -> str | None:
        """配对标识：dglab 中继的 controllerId；BLE 恒 None（无二维码）。"""
        return None

    def client_state(self) -> dict | None:
        """当前被控方的 props/slotState/devices（dglab 用；BLE 无则 None）。"""
        return None

    def to_state(self) -> dict:
        """状态上报：镜像现网 relay.to_state 字段（status/controller_id/url/clients/last_error）
        + backend 名 + scanned 列表，供前端不炸。"""
        return {
            "status": STATUS_DISCONNECTED,
            "controller_id": None,
            "url": "",
            "clients": [],
            "last_error": "",
            "backend": self.name,
            "scanned": [],
        }

    # ---------- 断开回调 ----------
    def on_disconnect(self, cb) -> None:
        """注册「设备/链路断开」回调（上层在此做自动清零与广播）。"""
        if cb not in self._disconnect_cbs:
            self._disconnect_cbs.append(cb)

    def _notify_disconnect(self, payload: dict | None = None) -> None:
        # 注册的回调可能是 async（如 AppState._on_backend_disconnect）：同步上下文里
        # 直接调只会生成协程对象、函数体永不执行 → 检测到协程则交给事件循环调度。
        for cb in list(self._disconnect_cbs):
            try:
                result = cb(payload or {})
                if asyncio.iscoroutine(result):
                    asyncio.ensure_future(result)
            except Exception:  # noqa: BLE001
                pass
