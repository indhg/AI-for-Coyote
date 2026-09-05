# -*- coding: utf-8 -*-
"""run 状态（D2 §4.1 / S3 §一）与钳制。全新字段，不存在 heat/will/affinity。"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict

from . import constants as C
from .rng import RunRNG


def stage_index(stage: str) -> int:
    return C.MARK_STAGES.index(stage)


def clamp(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, int(v)))


@dataclass
class RunState:
    yin_hua: int = 0
    e_duo: int = 0
    ma: int = 0
    ma_cap: int = C.MA_CAP_HUMAN
    str: int = 1
    dex: int = 1
    int: int = 1
    hp: int = C.HP_MAX
    mp: int = C.MP_MAX
    mark_stage: str = "none"
    crossed_gate: bool = False
    defected: bool = False
    dice: str = C.DEFAULT_DICE
    ability: list = field(default_factory=list)   # 首批空；ability_up 忽略
    flags: dict = field(default_factory=dict)     # key=英文标识 → 说明

    # ---------- 构造 ----------
    @classmethod
    def roll_new(cls, rng: RunRNG) -> "RunState":
        """开局：三维各 1-10 roll（顺序 str→dex→int，run RNG，入档）。"""
        s = cls()
        s.str = rng.randint(C.ATTR_ROLL_MIN, C.ATTR_ROLL_MAX)
        s.dex = rng.randint(C.ATTR_ROLL_MIN, C.ATTR_ROLL_MAX)
        s.int = rng.randint(C.ATTR_ROLL_MIN, C.ATTR_ROLL_MAX)
        return s

    # ---------- 钳制（每次结算后全量） ----------
    def clamp_all(self) -> None:
        self.ma = max(C.MA_MIN, int(self.ma))
        self.hp = clamp(self.hp, 0, C.HP_MAX)
        self.mp = clamp(self.mp, 0, C.MP_MAX)
        self.str = clamp(self.str, C.ATTR_MIN, C.ATTR_MAX)
        self.dex = clamp(self.dex, C.ATTR_MIN, C.ATTR_MAX)
        self.int = clamp(self.int, C.ATTR_MIN, C.ATTR_MAX)
        self.yin_hua = clamp(self.yin_hua, C.AXIS_MIN, C.AXIS_MAX)
        self.e_duo = clamp(self.e_duo, C.AXIS_MIN, C.AXIS_MAX)
        if self.mark_stage not in C.MARK_STAGES:
            self.mark_stage = "none"
        if self.dice not in C.DICE:
            self.dice = C.DEFAULT_DICE

    # ---------- 查询 ----------
    def stage_at_least(self, stage: str) -> bool:
        return stage_index(self.mark_stage) >= stage_index(stage)

    def attr(self, name: str) -> int:
        return int(getattr(self, name))

    def ma_tier(self) -> str:
        """HUD 用魔化档位（直接看 ma）。"""
        if self.ma >= C.MO_HUA_INSTANT:
            return "instant"
        if self.ma >= C.MO_HUA_FAST:
            return "fast"
        if self.ma >= C.MO_HUA_SLOW:
            return "slow"
        if self.ma >= C.MO_HUA_BUFFER:
            return "buffer"
        return "human"

    # ---------- 序列化 ----------
    def to_dict(self, en: bool = False) -> dict:
        """en=True 时 dice_name/dice_desc 用英文（D11 E5）；存档仍用默认中文（from_dict 不读这两项）。"""
        d = asdict(self)
        d["ma_tier"] = self.ma_tier()
        d["dice_name"] = (C.DICE_NAME_EN if en else C.DICE_NAME_ZH)[self.dice]
        d["dice_desc"] = (C.DICE_DESC_EN if en else C.DICE_DESC_ZH)[self.dice]
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "RunState":
        s = cls()
        for k in ("yin_hua", "e_duo", "ma", "ma_cap", "str", "dex", "int", "hp", "mp"):
            if k in d:
                setattr(s, k, int(d[k]))
        s.mark_stage = str(d.get("mark_stage", "none"))
        s.crossed_gate = bool(d.get("crossed_gate", False))
        s.defected = bool(d.get("defected", False))
        s.dice = str(d.get("dice", C.DEFAULT_DICE))
        s.ability = list(d.get("ability") or [])
        s.flags = dict(d.get("flags") or {})
        s.clamp_all()
        return s
