# -*- coding: utf-8 -*-
"""紫金地牢 v2 引擎（D2 从零重来版）。

对外只暴露 DungeonRuntime（挂进 main.py 的 /api/dungeon/* 路由）与 DungeonError。
内部模块：
    constants   枚举 / 阈值常数 / render 映射表
    rng         run PRNG（装配 + 骰子，state 入档）+ SHA-256 变体索引
    state       run 状态（§4.1）+ 钳制
    effects     effects grammar 结算
    checks      属性检定（attr + 骰子加成 ≥ TN）
    schema      内容格式校验器（fail-closed）
    loader      主题包加载（manifest / theme / events / bindings / base_setting）
    narrative   变体选择 + 叙事文本
    feedback    体感执行器（唯一出口 = SafetyManager.validate → send → record）
    engine      结算顺序 / 败北 / crossed_gate / 结局
    save        存档（含 rng_state + seed）
    render      HTTP render 结构
    runtime     DungeonRuntime（HTTP 壳对接）
    selftest    自测（python -m backend.dungeon_v2.selftest）
    autoplay    自动通关（python -m backend.dungeon_v2.autoplay）
    lint_words  禁词扫描（python -m backend.dungeon_v2.lint_words）
"""
from .errors import DungeonError
from .runtime import DungeonRuntime

__all__ = ["DungeonRuntime", "DungeonError"]
