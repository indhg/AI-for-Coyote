# -*- coding: utf-8 -*-
"""设备指令帧封装：把安全层校验后的命令转成 dglab-websocket-server V4 RPC 帧。

帧格式（已核对 dglab-kit / dglab-websocket-server 源码）：
  控制方 -> 服务器: {"type":"message","clientId":被控方ID,"data":{"t":"req","reqId":...,"m":"device.op","data":{...}}}
  device.op 动作类型:
    t=0 AppendPulseData  波形帧（v: 十六进制帧列表，d: 时长ms）
    t=3 AddIntensity     相对增减强度（v: 变化量）
    t=4 SetTempIntensity 临时强度（v: 值，d: 时长ms，到时自动归零）
    t=7 SetIntensity     绝对强度（仅支持 v=0，即归零）
  清理: m="device.op.clear"，data 可为 {"s":slotId, "c":通道} 或省略(清全部)
"""
import itertools

# 动作类型
ACT_APPEND = 0  # 波形
ACT_ADD = 3     # 相对增减强度
ACT_TEMP = 4    # 临时强度
ACT_SET = 7     # 绝对强度（归零）

CHANNEL = {"A": 0, "B": 1}
CHANNEL_NAME = {0: "A", 1: "B"}


class DeviceOps:
    """生成 V4 RPC 帧，维护 reqId 自增。"""

    def __init__(self) -> None:
        self._counter = itertools.count(1)

    def _req(self, method: str, data: dict | None, client_id: str) -> dict:
        inner: dict = {"t": "req", "reqId": str(next(self._counter)), "m": method}
        if data is not None:
            inner["data"] = data
        return {"type": "message", "clientId": client_id, "data": inner}

    @staticmethod
    def _op_data(
        slot_id: str,
        channel: int,
        action_type: int,
        value=None,
        duration_ms: int | None = None,
        immediate: bool | None = None,
    ) -> dict:
        data: dict = {"s": slot_id, "c": channel, "t": action_type}
        if duration_ms is not None:
            data["d"] = int(duration_ms)
        if value is not None:
            data["v"] = value
        if immediate:
            data["im"] = True
        return data

    def add_strength(
        self, client_id: str, slot_id: str, channel: int, delta: int,
    ) -> dict:
        """相对增减强度（V4 里最可靠的原语；绝对强度靠它换算差值实现）。"""
        return self._req(
            "device.op",
            self._op_data(slot_id, channel, ACT_ADD, delta),
            client_id,
        )

    def reset_intensity(
        self, client_id: str, slot_id: str, channel: int,
    ) -> dict:
        """强度归零（t=7, v=0）。"""
        return self._req(
            "device.op",
            self._op_data(slot_id, channel, ACT_SET, 0),
            client_id,
        )

    def pulse(
        self, client_id: str, slot_id: str, channel: int,
        frames: list[str], duration_ms: int, immediate: bool = True,
    ) -> dict:
        """下发波形帧（V3 帧格式十六进制字符串列表）。"""
        return self._req(
            "device.op",
            self._op_data(slot_id, channel, ACT_APPEND, frames, duration_ms, immediate),
            client_id,
        )

    def clear(
        self, client_id: str, slot_id: str | None = None,
        channel: int | None = None,
    ) -> dict:
        """清理任务：可清全部 / 指定设备 / 指定设备指定通道。"""
        data = None
        if slot_id is not None:
            data = {"s": slot_id}
            if channel is not None:
                data["c"] = channel
        return self._req("device.op.clear", data, client_id)

    def request_devices(self, client_id: str) -> dict:
        """请求设备列表。"""
        return self._req("devices.get", None, client_id)
