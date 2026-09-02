# -*- coding: utf-8 -*-
"""地牢叙事生成：LLM 扩写事件叙事；API 断/超时/无 LLM → 回退作者 seed（绝不空白）。

叙事是地牢里**唯一**依赖 API 的一环；结构（选项/分支/反馈）都是本地事件表/绑定表。

上下文分层注入（T030 #5 定稿）：
- L0 地牢基调（base_summary，固定 ≤400 字）：紫金地牢世界观/系统口吻/急停优先/淫纹核心
- L1 主题口吻（theme_tone，单包）：当前节点主题的 tone（触手咕啾~、品评会宣读）
- L2 事件事实锚点（seed/facts/taboo）：不可截断
- 已发生（run_memory）：最近 1~2 条选择，跨节点记忆
"""
from __future__ import annotations

import logging
import re

logger = logging.getLogger("ai-for-coyote.dungeon.narrative")


class NarrativeWriter:
    """事件叙事生成器。llm 可为 None（=永远离线降级，dry_run 自检用）。"""

    def __init__(self, llm=None, base_summary: str = "", dm_prompt: str = ""):
        self.llm = llm
        self.base_summary = (base_summary or "").strip()
        self.dm_prompt = dm_prompt.strip()

    async def narrate(
        self,
        event: dict,
        *,
        player_input: str | None = None,
        player_nick: str = "小柳",
        theme_label: str = "",
        theme_tone: str = "",
        run_memory: list | None = None,
        visit_n: int = 1,
        mark_flaring: bool = False,
        heat: int = 0,
    ) -> dict:
        """返回 {"text": str, "source": "llm"|"seed"}。

        - narrative.mode == fixed：seed 即全文，零 API。
        - seed_and_improvise / ai_only：先试 LLM，失败回退 seed（无 seed 回退标题）。
        """
        n = event.get("narrative") or {}
        mode = n.get("mode", "seed_and_improvise")
        seed = str(n.get("seed") or "").strip()
        variants = n.get("variants") or []
        fallback = seed or (str(variants[0]).strip() if variants else "") or str(event.get("title") or "").strip() or "……"

        if mode == "fixed":
            return {"text": fallback, "source": "seed"}

        if self.llm is not None:
            try:
                text = await self._call_llm(
                    event, n, player_input, player_nick, theme_label, theme_tone, run_memory,
                )
                if text and text.strip():
                    return {"text": text.strip(), "source": "llm"}
            except Exception as exc:  # noqa: BLE001 - 任何 API 异常都降级，不影响推进
                logger.warning("叙事 LLM 调用失败，回退 seed：%s", exc)

        return {"text": self._offline_overlay(
            self._render_slots(fallback, player_nick=player_nick, heat=heat),
            player_input=player_input, visit_n=visit_n, mark_flaring=mark_flaring,
        ), "source": "seed"}

    @staticmethod
    def _render_slots(text: str, *, player_nick: str, heat: int) -> str:
        tiers = ((30, "余温"), (60, "微热"), (85, "发烫"), (101, "想被填"))
        heat_tier = next(label for limit, label in tiers if int(heat) < limit)

        def replace(match):
            key = match.group(1)
            if key == "nick":
                return player_nick
            if key == "heat_tier":
                return heat_tier
            logger.warning("未知叙事插槽，保留原文：{%s}", key)
            return match.group(0)

        return re.sub(r"\{([^{}]+)\}", replace, text)

    @staticmethod
    def _offline_overlay(text: str, *, player_input: str | None, visit_n: int, mark_flaring: bool) -> str:
        lines = []
        if int(visit_n) >= 2:
            lines.append("这间你来过。")
        if mark_flaring:
            lines.append("小腹那栏还亮着，想要。")
        if player_input and player_input.strip():
            lines.append("你刚才：" + player_input.strip()[:20])
        return text if not lines else text + "\n\n" + "\n".join(lines)

    async def _call_llm(
        self, event: dict, n: dict, player_input, player_nick,
        theme_label: str, theme_tone: str, run_memory,
    ) -> str:
        facts = n.get("facts") or []
        taboo = n.get("taboo") or []
        seed = str(n.get("seed") or "").strip()
        title = str(event.get("title") or "").strip()

        system_lines = [
            f"你是「{theme_label or '地牢'}」的叙事者（地牢主）。只写一段叙事描写，"
            "不要输出 JSON、不要提及设备参数/强度/波形/通道，不要发明事件或选项。",
        ]
        # L0 地牢基调（固定骨架卡，不随主题拼接）
        if self.base_summary:
            system_lines.append(f"【地牢基调（所有主题共用）】{self.base_summary[:400]}")
        elif self.dm_prompt:
            system_lines.append(f"【文风参考】{self.dm_prompt[:600]}")
        # L1 当前主题口吻（单包）
        if theme_tone:
            system_lines.append(f"【主题口吻（仅本节点）】{theme_tone}")
        # L2 事件事实锚点（不可截断）
        if seed:
            system_lines.append(f"【本事件事实锚点（必须体现，不可推翻）】{seed}")
        if facts:
            system_lines.append("【固定事实】" + "；".join(str(f) for f in facts))
        if taboo:
            system_lines.append("【禁止方向】" + "；".join(str(t) for t in taboo))
        # 跨节点记忆（最近选择）
        if run_memory:
            labels = "；".join(str(m.get("label") or m.get("choice_id") or "") for m in run_memory[-2:])
            if labels:
                system_lines.append(f"【已发生】玩家刚在上一处：{labels}")
        system = "\n".join(system_lines)

        action = player_input.strip() if player_input else "（开场，你刚刚进入这里）"
        user = (
            f"当前事件：{title}\n"
            f"玩家「{player_nick}」刚刚：{action}\n"
            "请用第二人称「你」写一段 80~160 字的叙事描写（动作/环境描写用（）括起来），只输出描写文本本身。"
        )
        return await self.llm.complete(system, user, max_tokens=600)
