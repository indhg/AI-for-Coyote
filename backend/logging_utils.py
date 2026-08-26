# -*- coding: utf-8 -*-
"""运行日志：控制台 + app.log（仅程序运行错误/状态，无复盘日志）。"""
import logging
from pathlib import Path


def setup_logging(log_dir: str, level: str = "INFO") -> logging.Logger:
    logger = logging.getLogger("ai-for-coyote")
    if logger.handlers:  # 避免重复初始化
        return logger
    logger.setLevel(getattr(logging, str(level).upper(), logging.INFO))

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    logger.addHandler(console)

    Path(log_dir).mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(
        Path(log_dir) / "app.log", encoding="utf-8"
    )
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)
    return logger
