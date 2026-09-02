# -*- coding: utf-8 -*-
"""按 config 构造设备后端（T043 §B factory）。

config 示例：
    device:
      backend: dglab_relay     # 或 coyote2_ble
      ble:
        adapter: auto
        device_name_prefix: "D-LAB ESTIM"
        preferred_address: ""          # 上次成功的 MAC/UUID，可跳过选择
        swap_wave_chars: false         # 官方表 A/B 波形特性对调（真机判定后改）
        wave_xy: [1, 10]               # XYZ 的 X/Y 默认（听感校准项）
        # UUID 覆盖（留空=官方文档自动拼；真机枚举不一致时填完整 UUID）
        svc_pwm: ""
        char_ab2: ""
        char_a: ""
        char_b: ""
"""
from __future__ import annotations

import logging

logger = logging.getLogger("ai-for-coyote.device.factory")


def build_backend(cfg, safety, on_event=None, on_action=None):
    """构造配置指定的后端；默认 dglab_relay（现有用户零行为变化）。"""
    device_cfg = (cfg.get("device") or {}) if isinstance(cfg, dict) else {}
    backend_name = str(device_cfg.get("backend") or "dglab_relay").strip().lower()

    if backend_name == "coyote2_ble":
        from .coyote2_ble import Coyote2BleBackend

        backend = Coyote2BleBackend(cfg, safety, on_event=on_event, on_action=on_action)
    elif backend_name in ("dglab_relay", "dglab", ""):
        from .dglab_relay import DGLabRelayBackend

        backend = DGLabRelayBackend(cfg, safety, on_event=on_event, on_action=on_action)
    else:
        raise ValueError(
            f"未知 device.backend: {backend_name!r}（支持 dglab_relay / coyote2_ble）"
        )
    logger.info("设备后端: %s", backend.name)
    return backend
