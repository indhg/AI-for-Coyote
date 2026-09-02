# -*- coding: utf-8 -*-
"""M2 地牢骨架（dry_run）：纯叙事事件环 + 可复现随机池 + 存档续局。

本包是「地牢」板块的后端运行时骨架，属 M2 阶段：只做 dry_run（设备动作只校验不真发），
不接入 main.py 的运行时路径。加载与校验复用 M1 的 story_pack。
"""
from .loader import ThemePack, PackLoadError, load_pack
from .engine import DungeonEngine, RunError, new_run
from .narrative import NarrativeWriter
from .feedback import resolve_feedback
from .executor import FeedbackExecutor
from .save import save_run, load_run

__all__ = [
    "ThemePack",
    "PackLoadError",
    "load_pack",
    "DungeonEngine",
    "RunError",
    "new_run",
    "NarrativeWriter",
    "resolve_feedback",
    "FeedbackExecutor",
    "save_run",
    "load_run",
]
