# -*- coding: utf-8 -*-
"""设备后端抽象层（T043 落地）：多设备接入的统一门面。

结构：
- base.py           DeviceBackend 接口 + 状态常量
- dglab_relay.py    现网 dglab-websocket-server v4 桥 adapter（行为零变化）
- coyote2_ble.py    郊狼 v2（ESTIM01）BLE 直连 adapter（主项，需真机勾待实测项）
- v2_codec.py       V2 协议编解码（强度位域/XYZ/UI 映射）
- factory.py        按 config 构造后端
"""
from .base import (
    CHANNEL,
    CHANNEL_NAME,
    STATUS_CONNECTING,
    STATUS_DISCONNECTED,
    STATUS_PAIRED,
    STATUS_READY,
    STATUS_WAITING,
    DeviceBackend,
)
from .factory import build_backend

__all__ = [
    "CHANNEL",
    "CHANNEL_NAME",
    "STATUS_CONNECTING",
    "STATUS_DISCONNECTED",
    "STATUS_PAIRED",
    "STATUS_READY",
    "STATUS_WAITING",
    "DeviceBackend",
    "build_backend",
]
