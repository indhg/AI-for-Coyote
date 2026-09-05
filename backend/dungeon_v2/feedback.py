# -*- coding: utf-8 -*-
"""体感执行器：事件 feedback（节奏意图）→ bindings 动作模板 → SafetyManager.validate → send → record。

铁律：
- 所有设备动作必须经 safety.validate 拿到内部 cmd，再 send（backend.apply），再 safety.record；
- 急停中 safety.validate 自己拒绝（「急停中，拒绝一切设备动作」），这里不绕；
- 叙事里没有任何强度/通道数字，数字只在 bindings.json 与这里；
- dry_run（cfg.app.dry_run）或未接 send → 不发真机，只 record（与 game_loop 一致）；
- 数值扰动 ±20% 用独立真随机（不入档，读档数值可不同——S1 §4.3 允许）。

EN：设备反馈文案走 ui_en.describe_en / reason_en / hint_en（本模块不自造设备 EN 文案；
hint_en 不认识的核心词回退到本地表，见 _HINT_EN_FALLBACK，需主 Agent 补进 ui_en.py）。
"""
from __future__ import annotations

import logging
import random

from . import constants as C
from .schema import parse_feedback

logger = logging.getLogger("ai-for-coyote.dungeon_v2.feedback")

try:
    from ..ui_en import describe_en, reason_en, hint_en  # type: ignore
except Exception:  # noqa: BLE001  # 独立测试环境无 ui_en：退化为原样
    def describe_en(cmd: dict) -> str:  # type: ignore
        return str(cmd.get("kind"))

    def reason_en(zh: str) -> str:  # type: ignore
        return zh

    def hint_en(hint: str) -> str:  # type: ignore
        return hint

# ui_en.hint_en 目前只认 无/轻微/持续/已清理；以下核心词需主 Agent 补进 ui_en._HINT_EN
_HINT_EN_FALLBACK = {"无": "none", "试探": "tease", "持续": "steady", "连击": "combo", "停顿": "pause", "清理": "cleared"}


def hint_text(core: str, en: bool) -> str:
    if not en:
        return core
    out = hint_en(core)
    if out == core:
        out = _HINT_EN_FALLBACK.get(core, core)
    return out


def _describe_zh(cmd: dict) -> str:
    kind, ch = cmd.get("kind"), cmd.get("channel")
    if kind == "temp":
        return f"{ch} 通道临时强度 {cmd.get('value')}，{cmd.get('duration_s', 0):.1f}s"
    if kind == "hold":
        return f"{ch} 通道持续强度 {cmd.get('value')}"
    if kind == "add":
        return f"{ch} 通道增减 {cmd.get('delta', 0):+d}"
    if kind == "pulse":
        return f"{ch} 通道波形「{cmd.get('pattern')}」{cmd.get('duration_s', 0):.1f}s"
    if kind == "clear":
        return "清除全部" if ch is None else f"清除 {ch} 通道"
    if kind == "stop":
        return "全部清零"
    return str(kind)


class FeedbackExecutor:
    """main.py 只会设置 executor.send = backend.apply（async cmd→bool）。"""

    def __init__(self, cfg, safety) -> None:
        self.cfg = cfg
        self.safety = safety
        self.send = None                 # async callable(cmd) -> bool；None = 没接真机
        self._fx = random.Random()       # 数值扰动专用真随机（不入档）

    # ---------- 语言 / dry_run ----------
    def _en(self) -> bool:
        try:
            return str(self.cfg["character"].get("lang") or "zh") == "en"
        except Exception:  # noqa: BLE001
            return False

    def _dry_run(self) -> bool:
        if self.safety is not None and hasattr(self.safety, "dry_run"):
            return bool(self.safety.dry_run)
        try:
            return bool(self.cfg["app"].get("dry_run", True))
        except Exception:  # noqa: BLE001
            return True

    # ---------- 规划 ----------
    def plan(self, bindings: dict, event: dict, cores: list[str] | None = None) -> tuple[list[str], list[dict]]:
        """把事件 feedback 解析成核心词序列，并按 bindings 展开成动作列表（已填 $strength）。"""
        if cores is None:
            cores = parse_feedback(event.get("feedback", ""))
        band = str(event.get("band", "entry"))
        inten = str(event.get("intensity", "none"))
        base = int(bindings.get("band_strength", {}).get(band, 0))
        scale = float(bindings.get("intensity_scale", {}).get(inten, 0))
        actions: list[dict] = []
        for core in cores:
            spec = (bindings.get("rhythm") or {}).get(core) or {}
            for tpl in spec.get("actions") or []:
                a = dict(tpl)
                if a.get("value") == "$strength":
                    a["value"] = self._strength(base, scale, a.get("channel"))
                a["_core"] = core
                actions.append(a)
        return cores, actions

    def _strength(self, base: int, scale: float, channel) -> int:
        v = base * scale
        if v <= 0:
            return 0
        jitter = 1.0 + self._fx.uniform(-C.PERTURB_PCT, C.PERTURB_PCT) / 100.0
        v = int(round(v * jitter))
        cap = 100
        if self.safety is not None and channel in ("A", "B"):
            try:
                cap = int(self.safety.cap_for(channel))
            except Exception:  # noqa: BLE001
                cap = 100
        return max(0, min(v, cap))

    # ---------- 执行 ----------
    async def run(self, actions: list[dict]) -> tuple[list[dict], list[dict]]:
        """逐条 validate → send → record。返回 (executed, dropped)，结构与 game_loop 对齐。"""
        executed: list[dict] = []
        dropped: list[dict] = []
        if self.safety is None:
            for a in actions:
                dropped.append({"action": _public(a), "reason": "no safety layer"})
            return executed, dropped
        en = self._en()
        dry = self._dry_run()
        for a in actions:
            action = _public(a)
            ok, reason, cmd = self.safety.validate(action)
            if not ok or cmd is None:
                dropped.append({"action": action, "reason": reason_en(reason) if en else reason})
                continue
            sent = False
            if not dry and self.send is not None:
                try:
                    sent = bool(await self.send(cmd))
                except Exception as exc:  # noqa: BLE001
                    logger.warning("地牢体感发送失败：%s", exc)
                    sent = False
            self.safety.record(cmd)
            executed.append({
                "action": action,
                "reason": reason_en(reason) if en else reason,
                "sent": sent,
                "label": describe_en(cmd) if en else _describe_zh(cmd),
            })
        return executed, dropped

    async def cleanup(self) -> tuple[list[dict], list[dict]]:
        """【清理设备】：clear 全部 + stop。败北 / ending / 安全区都走这里。"""
        return await self.run([{"op": "clear"}, {"op": "stop"}])


def _public(a: dict) -> dict:
    return {k: v for k, v in a.items() if not k.startswith("_")}
