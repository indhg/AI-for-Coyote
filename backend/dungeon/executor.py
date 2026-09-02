# -*- coding: utf-8 -*-
"""地牢反馈执行器（M3）：绑定动作 → SafetyManager 校验/钳制/记录。

复用与自由聊同一套安全层（SafetyManager.validate + record），保证地牢体感
也走「唯一出口」，享受相同的强度上限/步长/时长/过热/急停/通道开关钳制。
dry_run=True 时只校验+记录，不真发设备；真机发送回调（send）在 M4 接入中继时提供。
"""
from __future__ import annotations

import logging

from ..ui_en import describe_en, reason_en

logger = logging.getLogger("ai-for-coyote.dungeon.executor")


class FeedbackExecutor:
    """把反馈动作逐条过安全层。"""

    def __init__(self, safety, dry_run: bool = True, send=None, en: bool = False):
        self.safety = safety
        self.dry_run = bool(dry_run)
        self.send = send  # async (cmd) -> bool，真机执行回调
        self.en = bool(en)  # EN 模式：执行说明/拒绝原因走英文（T051 §1.5/§4.2）

    async def execute(self, actions: list[dict]) -> dict:
        """执行 on_enter 反馈动作，返回 {executed, dropped}。"""
        return await self._run(actions)

    async def cleanup(self, actions: list[dict]) -> dict:
        """执行 on_exit/cleanup 动作（clear/stop 等收尾）。"""
        return await self._run(actions)

    async def _run(self, actions: list[dict]) -> dict:
        executed, dropped = [], []
        en = self.en
        for a in actions or []:
            if not isinstance(a, dict):
                dropped.append(
                    {
                        "action": a,
                        "reason": reason_en("动作必须是对象") if en else "动作必须是对象",
                    }
                )
                continue
            ok, reason, cmd = self.safety.validate(a)
            if not ok:
                if en:
                    reason = reason_en(reason)
                dropped.append({"action": a, "reason": reason})
                logger.warning("地牢反馈被安全层拒绝：%s -> %s", a, reason)
                continue
            self.safety.record(cmd)
            label = describe_en(cmd) if en else _describe(cmd)
            sent = False
            if self.send and not self.dry_run:
                try:
                    sent = bool(await self.send(cmd))
                except Exception:  # noqa: BLE001
                    logger.exception("地牢反馈真机发送失败")
                    sent = False
            executed.append({"action": a, "reason": reason, "cmd": cmd, "label": label, "sent": sent})
            logger.info(
                "%s地牢反馈：%s（%s）",
                "DRY-RUN " if (self.dry_run or not sent) else "",
                label,
                "已发送" if sent else "模拟",
            )
        return {"executed": executed, "dropped": dropped}


def _describe(cmd: dict) -> str:
    kind = cmd.get("kind")
    ch = cmd.get("channel")
    if kind == "temp":
        return f"{ch} 爆发 {cmd.get('value')} × {cmd.get('duration_s', 0):.1f}s（结束归零）"
    if kind == "hold":
        return f"{ch} 持续强度 {cmd.get('value')}（保持）"
    if kind == "add":
        return f"{ch} 增减 {cmd.get('delta', 0):+d}"
    if kind == "pulse":
        return f"{ch} 波形「{cmd.get('pattern')}」× {cmd.get('duration_s', 0):.1f}s"
    if kind == "pulse_hold":
        return f"{ch} 持续波形「{cmd.get('pattern')}」（循环）"
    if kind == "clear":
        return "清除全部" if ch is None else f"清除 {ch} 通道"
    return "急停清零"
