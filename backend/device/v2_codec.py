# -*- coding: utf-8 -*-
"""郊狼 v2（脉冲主机 V2 / D-LAB ESTIM01）BLE 协议编解码（T043 §C）。

协议来源：DG-LAB-OPENSOURCE coyote/v2 公开文档 + 社区实现对照。
凡官方文档含糊处一律标注「待实测」，落地时以真机 GATT 枚举为准。

已实现（可写进代码、单测可覆盖的部分）：
- UI 0-200 ↔ V2 强度 S 0-2047（官方上限 2047；PWM_AB2 位域 bit21-11=A、bit10-0=B）
- PWM_AB2 / XYZ 特性 3 字节打包解包
- V3 波形帧（8 字节 hex，A/B 各 4 个 25ms 子点）→ 单通道 XYZ 的折取（每 100ms 一拍）

待实测（真机勾掉，勿在代码里写死依赖）：
- 完整 UUID 拼接（短号 0x180A/0x180B/0x1500/0x1504/0x1505/0x1506 vs 标准 UUID）
- 官方表 PWM_A34 / PWM_B34 通道对调嫌疑 → 配置 swap_wave_chars
- 官方 App 圆环数字是否 0-200；Z 档手感（V3 强度 ≈ Z×5 的听感）
"""
from __future__ import annotations

# UI 上限（与现网 safety 一致：0-200）
UI_MAX = 200
# V2 强度硬件上限（PWM_AB2 每通道 11bit）
S_MAX = 2047
# 官方 App 波形相对强度范围 0-20
Z_MAX = 20

# 基础 UUID：955Axxxx-0FE2-F5AA-A094-84B8D4F3E8AD（xxxx=服务短号，待实测拼接规则）
UUID_BASE = "955A{short:04x}-0FE2-F5AA-A094-84B8D4F3E8AD"

# 服务/特性短号（DG-LAB 官方 coyote/v2 文档；待实测：短号是 180A/180B 还是 1500 等，以真机枚举为准）
SVC_BATTERY_SHORT = 0x180A
SVC_PWM_SHORT = 0x180B          # 强度/波形所在服务
CHAR_BATTERY_SHORT = 0x1500     # 1 字节 0-100，读/通知
CHAR_PWM_AB2_SHORT = 0x1504     # 3 字节 A/B 强度，读/写/通知
CHAR_PWM_A34_SHORT = 0x1505     # 3 字节波形（官方表标注 A 通道波形；待实测对调）
CHAR_PWM_B34_SHORT = 0x1506     # 3 字节波形（官方表标注 B 通道波形；待实测对调）

# 波形写环节拍（官方窗口 100ms，与现网 V3 4×25ms 同一拍）
FRAME_MS = 100


def svc_uuid(short: int) -> str:
    """按文档把短号拼进自定义基础 UUID（待实测：真机枚举为准）。"""
    return UUID_BASE.format(short=short)


def ui_to_s(value: int) -> int:
    """UI 强度 0-200 → V2 S 0-2047，钳制 ≤2047。"""
    try:
        v = int(float(value))
    except (TypeError, ValueError):
        v = 0
    return max(0, min(S_MAX, round(v * S_MAX / UI_MAX)))


def s_to_ui(s: int) -> int:
    """V2 S → UI 0-200（设备上报显示用）。"""
    return max(0, min(UI_MAX, round(int(s) * UI_MAX / S_MAX)))


def pack_ab2(a_s: int, b_s: int) -> bytes:
    """A/B 强度打包 3 字节：bit21-11=A(11bit)，bit10-0=B(11bit)，bit23-22 保留。"""
    v = ((max(0, min(S_MAX, int(a_s))) & 0x7FF) << 11) | (max(0, min(S_MAX, int(b_s))) & 0x7FF)
    return v.to_bytes(3, "big")


def unpack_ab2(data: bytes | bytearray) -> tuple[int, int]:
    """解 3 字节 AB2 → (A_S, B_S)。"""
    v = int.from_bytes(bytes(data)[:3], "big")
    return ((v >> 11) & 0x7FF), (v & 0x7FF)


def pack_xyz(x: int, y: int, z: int) -> bytes:
    """XYZ 打包 3 字节：bit23-20 保留；bit19-15=Z(5bit)；bit14-5=Y(10bit)；bit4-0=X(5bit)。"""
    v = (
        ((max(0, min(Z_MAX, int(z))) & 0x1F) << 15)
        | ((max(0, min(1023, int(y))) & 0x3FF) << 5)
        | (max(0, min(31, int(x))) & 0x1F)
    )
    return v.to_bytes(3, "big")


def unpack_xyz(data: bytes | bytearray) -> tuple[int, int, int]:
    v = int.from_bytes(bytes(data)[:3], "big")
    return (v & 0x1F), ((v >> 5) & 0x3FF), ((v >> 15) & 0x1F)


def v3_frame_to_xyz(hex_frame: str, channel: str, x_default: int = 1,
                    y_default: int = 10, strength_scale: float = 5.0) -> tuple[int, int, int]:
    """现网 V3 波形帧（8 字节 hex，A/B 各 4 个 25ms 子点）→ 该通道一个 XYZ。

    V3 帧 100ms 窗口内的 4 个子点折成一个 XYZ：Z 取子点均值的 1/strength_scale
    （官方近似：V3 强度 ≈ Z×5）；X/Y 用配置默认（待实测：听感不符则调）。
    帧样例：'0A0A0A0A00000000' → A 通道 4×25ms=10，B 通道=0。
    """
    try:
        raw = bytes.fromhex(hex_frame)
    except ValueError:
        raw = bytes(8)
    raw = (raw + bytes(8))[:8]
    ch0 = 0 if channel == "A" else 4
    vals = [raw[i] for i in range(ch0, ch0 + 4)]  # 0-100 强度
    avg = sum(vals) / 4.0
    z = max(0, min(Z_MAX, int(round(avg / strength_scale))))
    return int(x_default), int(y_default), z


def wave_zero_xyz() -> tuple[int, int, int]:
    """停止波形用：X=0（无脉冲）。"""
    return 0, 0, 0
