# -*- coding: utf-8 -*-
"""枚举、阈值常数、render 映射（S1 §五 / S3 §一 / D2 §4.6，冻结口径，无旧值兼容）。

阈值常数一律写在这里，不藏进文案。
"""
from __future__ import annotations

# ---------- 内容格式 ----------
PACK_FORMAT = "dungeon_v2"          # manifest.format
PACK_FORMAT_VERSION = 1             # manifest.format_version
SAVE_FORMAT = "dungeon_v2_save"     # 存档 format 标记
SAVE_VERSION = 2
SAVE_VERSIONS_READ = (1, 2)  # v1=chain-only；v2=可含 map 路网

END_TOKEN = "end"                   # ending choice 的 next 终止引用
MAP_RETURN = "map"                  # map 模式：节点事件结算后回路网（非事件 id）
PACK_MODE_CHAIN = "chain"
PACK_MODE_MAP = "map"
NODE_STATES = ("current", "reachable", "gated", "visited", "bypassed", "locked")

# ---------- 词表（§4.6，fail-closed） ----------
BANDS = ("entry", "mid", "upper", "lower", "end")
ROOMS = ("gate", "corridor", "encounter", "nest", "rest", "treasure", "trap", "boss", "ending")
KINDS = ("scene", "beat", "rest", "boss", "ending")
SETTLEMENTS = (
    "enter", "move", "take", "leave", "rest", "kill", "yield", "defeat",
    "escape", "fall", "end_escape", "end_stay", "end_sink",
)
INTENSITIES = ("none", "low", "medium", "medium-high", "high")
FEEDBACK_CORE = ("无", "试探", "持续", "连击", "停顿", "清理")
DICE = ("d1", "d4", "d6", "ed6")
DEFAULT_DICE = "d1"
DICE_DROP_POOL = ("d4", "d6", "ed6")   # E016 掉落池（d1 不进池）
MARK_STAGES = ("none", "bud", "appear", "form", "set")
ABILITY_RANKS = ("C", "B", "A", "S", "EX")
SPECIES_NONE = "无"

ENDING_BY_SETTLEMENT = {"end_escape": "escape", "end_stay": "stay", "end_sink": "sink"}

# ---------- render 映射（D2 §3.2） ----------
CONTENT_LEVEL_BY_INTENSITY = {"none": 0, "low": 1, "medium": 2, "medium-high": 3, "high": 4}
TIER_BY_BAND = {"entry": 1, "mid": 2, "upper": 3, "lower": 4, "end": 5}

# ---------- 状态范围（S3 §一 钳制） ----------
ATTRS = ("str", "dex", "int")
ATTR_ROLL_MIN, ATTR_ROLL_MAX = 1, 10       # 开局 roll
ATTR_MIN, ATTR_MAX = 1, 20                 # 本局内范围
HP_MAX = 10
MP_MAX = 10
AXIS_MIN, AXIS_MAX = 0, 100                # yin_hua / e_duo
MA_MIN = 0                                 # ma = max(0, ma)，不设上限
MA_CAP_HUMAN = 50                          # 首批不启用，只存字段

# ---------- 阈值常数（S1 §五） ----------
YIN_HUA_WILL_MAX = 24
YIN_HUA_TICKS = (25, 50, 75, 100)
E_DUO_TICKS = (25, 50, 75, 100)
MO_HUA_BUFFER = 100      # crossed_gate 用：ma >= 100
MO_HUA_SLOW = 200
MO_HUA_FAST = 300
MO_HUA_INSTANT = 500     # 首批不实现（不可达）
DEFECT_YIN = 75
DEFECT_E = 75
DEFECT_MA = 200          # 「魔化极深」建议值；首批只留判定不进事件
CONTRACT_MAX = 3
GATE_STAGE_MIN = "form"  # crossed_gate 需 mark_stage >= form

# ---------- 骰子（S4） ----------
DICE_MAX_BONUS = {"d1": 1, "d4": 4, "d6": 6, "ed6": 6}
ED6_ZERO_PCT = 15        # ed6 归零概率（百分数）

DICE_DESC_ZH = {"d1": "会是什么？", "d4": "重置自己", "d6": "重置你的命运", "ed6": "？？？"}
DICE_DESC_EN = {"d1": "What will it be?", "d4": "Reroll into something else",
                "d6": "Reroll your destiny", "ed6": "???"}
DICE_NAME_ZH = {"d1": "D1", "d4": "D4", "d6": "D6", "ed6": "永恒 D6"}
DICE_NAME_EN = {"d1": "D1", "d4": "D4", "d6": "D6", "ed6": "Eternal D6"}

# ---------- 检定 TN 分档（S1 §三） ----------
TN_EASY, TN_MED, TN_HARD, TN_EXTREME, TN_BOSS = 6, 8, 10, 12, 14
TN_BAND_RANGE = {           # 层带递进（validator 只告警不阻断）
    "entry": (6, 8), "mid": (6, 8), "upper": (8, 10), "lower": (10, 12), "end": (6, 15),
}
TN_BOSS_RANGE = (14, 15)

# ---------- require 键 ----------
REQUIRE_ATTR_KEYS = ATTRS
REQUIRE_GATE_KEYS = ("stage_min", "yin_hua_gte", "e_duo_gte", "ma_gte", "hp_gte", "mp_gte")
# mo_hua_gte（百分比门槛）首批不实现 → validator 拒绝（fail-closed）

# ---------- effects 键 ----------
EFFECT_DELTA_KEYS = ("yin_hua", "e_duo", "ma", "hp", "mp", "str", "dex", "int")
EFFECT_STAGE_KEYS = ("stage_bud", "stage_appear", "stage_form", "stage_set", "stage_down")
EFFECT_STAGE_TARGET = {"stage_bud": "bud", "stage_appear": "appear",
                       "stage_form": "form", "stage_set": "set"}
EFFECT_FLAG_KEYS = ("dice_gain", "ability_up")
EFFECT_META_KEYS = ("visit_n_eq",)

# ---------- 体感执行 ----------
FEEDBACK_ACTION_OPS = ("temp_strength", "hold_strength", "add_strength", "pulse", "clear", "stop")
# pulse_hold 需要 backend.start_pulse_hold，main.py 只给了 executor.send=backend.apply → 首批不允许
PERTURB_PCT = 20          # 数值扰动 ±20%（真随机，不入档）

LOG_MAX = 200             # run.log 保留条数
