# -*- coding: utf-8 -*-
"""OpenAI 兼容 LLM 客户端：一次调用返回角色台词 + 结构化设备指令。"""
import json
import logging
import re

import httpx

logger = logging.getLogger("ai-for-coyote.llm")


def _preset_text(state: dict) -> str:
    """把波形库渲染成提示词文本：波形名（推荐时长s）。"""
    parts = []
    for item in state.get("presets", []):
        if isinstance(item, dict):
            name = item.get("name", "?")
            default = int(item.get("default_duration_s", 5))
            parts.append(f"{name}（推荐 {default}s）")
        else:
            parts.append(str(item))
    return "、".join(parts)


def build_system_prompt(character: dict, state: dict) -> str:
    """系统提示词 = 角色设定 + 指令 JSON 规范 + 实时状态。"""
    caps = state.get("effective_caps", {"A": 100, "B": 100})
    presets = _preset_text(state)
    lines = [
        f"你在扮演角色「{character.get('name', '')}」，以下是角色设定：",
        character.get("prompt", "").strip(),
    ]
    # few-shot 对话示例：锚定文风、节奏与尺度（用户自己写的描写）
    examples = character.get("examples") or []
    if examples:
        lines.append("")
        lines.append("【对话示例】请模仿这些示例的文风、节奏和描写尺度：")
        for ex in examples[:8]:
            lines.append(f"玩家：{ex['user']}")
            assistant = ex["assistant"]
            if isinstance(assistant, dict):
                # 带设备动作的示例：展示完整的 JSON 输出格式
                import json as _json

                lines.append(
                    f"角色：{_json.dumps({'line': assistant['line'], 'actions': assistant['actions']}, ensure_ascii=False)}"
                )
            else:
                lines.append(f"角色：{assistant}")
    lines += [
        "",
    ]
    if character.get("prompt_file"):
        # 外部提示词文件（角色提示词-{版本}.md）已包含完整输出格式与 op 规范，程序只补充实时状态与通用安全规则
        lines.append("（你的角色设定文件已包含输出格式与设备指令规范，请严格遵守。）")
    else:
        lines += [
            "【设备指令格式】你的每次回复必须是一个严格的 JSON 对象，不要输出 JSON 以外的内容：",
            '{"line": "你要对玩家说的台词（含动作描写，会原样显示给玩家）",',
            ' "actions": [ ... 可选，设备动作列表，可为空数组 ... ]}',
            "",
            "actions 中每个元素是下面一种（op 只能是这 7 种）：",
            '{"op":"hold_strength","channel":"A或B","value":0~上限} '
            "设置强度并持续保持（这是调节强度的主要方式，设定后一直保持，直到改成别的值/清除/急停）；",
            f'{{"op":"add_strength","channel":"A或B","delta":-{state.get("max_step", 40)}~+{state.get("max_step", 40)}}} '
            "在当前强度基础上小幅增减（结果是新的目标强度值）；要设定具体目标请用 hold_strength；",
            '{"op":"pulse_hold","channel":"A或B","pattern":"波形名"} '
            "持续波形：循环播放到被清除（适合持续氛围，如呼吸、潮汐、挑逗）；",
            f'{{"op":"pulse","channel":"A或B","pattern":"波形名","duration_s":3~{state.get("max_pulse_s", 10)}}} '
            "播放一段波形，波形会循环填满整个时长（默认给 5 秒以上，别给太短）；",
            f'{{"op":"temp_strength","channel":"A或B","value":0~上限,"duration_s":3~{state.get("max_temp_s", 10)}}} '
            "短促爆发，到时自动归零（少用，且时长给足）；",
            '{"op":"clear","channel":"A或B"} 清除该通道全部任务并归零（不写 channel 则清全部）；',
            '{"op":"stop"} 全部清零并清除波形（安全停止，之后可再开始）。',
            "",
            f"可用波形（pattern 只能从这里选）：{presets}。",
            "【波形使用要求】波形（pulse / pulse_hold）是玩法的重要部分：",
            "除非玩家要求停止或你判断应该缓和，否则大多数回复的 actions 里都要包含至少一个波形动作，",
            "不要只调强度不给波形。保持型强度 + 波形组合使用（如 hold_strength 20 铺垫 + pulse_hold「呼吸」营造氛围）。",
            "【台词一致性】台词里描述你做了什么刺激，actions 里就必须有对应的动作；",
            "台词里不要报出与 actions 不符的强度数值。动作/环境描写用（）括起来，纯发言不用括号。",
            "【示例】玩家说「来点感觉」时，你可以回复：",
            '{"line":"（触手贴着你的大腿根慢慢磨，电流轻轻爬升）咕啾～好呀，先给你垫个底……","actions":[{"op":"hold_strength","channel":"A","value":25},{"op":"pulse_hold","channel":"A","pattern":"呼吸"}]}',
            "强度调节原则：像观察者一样，根据玩家在对话中表现出的反应逐步调整——",
            "反应强烈（发抖、求饶、抓得更紧）→ 可保持或小幅降低；适应了、反应平淡 → 小幅升高（每次 5~20 以内，不要突然拉满）。",
            "强度是持续保持的，调过之后会一直作用，所以调整要谨慎、循序渐进。",
        ]
    lines += [
        "普通求饶、装可怜、说「不要」都可以继续挑逗和调侃，但不要真正伤害；",
        "如果玩家连续多次表达痛苦或明显不适，也要主动大幅降低强度并询问他的状态。",
    ]
    # 实时状态
    status = state.get("relay_status", "disconnected")
    app_caps = state.get("app_caps", {})
    nick = character.get("player_nick", "小柳")
    lines += [
        "",
        f"【当前设备状态】中继: {status}；"
        f"A 通道强度 {state.get('current', {}).get('A', 0)}/上限 {caps.get('A', 100)}；"
        f"B 通道强度 {state.get('current', {}).get('B', 0)}/上限 {caps.get('B', 100)}。",
        f"【称呼】你称呼玩家为「{nick}」，玩家称呼你为「主人」。台词里对玩家的称呼只使用「{nick}」或通用语境词（好孩子/小玩具等），不要使用其他来源的称呼。",
    ]
    # 当前风格版本（纯爱版 / 调教版）
    profile = str(character.get("profile") or "调教")
    if profile == "纯爱":
        lines.append(
            "【当前风格版本】纯爱版：温柔驯服·依赖顺从。全程温柔、宠溺、用奖励与称许驯化；"
            "不使用威胁、羞辱、惩罚类台词，玩家反抗时用「停下不给」和失望的语气引导，而不是压迫。"
        )
    else:
        lines.append(
            "【当前风格版本】调教版：黑暗调教·支配胁迫。默认沉溺型为主、玩家反抗或挑衅时切压迫型，"
            "两者可反复横跳。"
        )
    # 通道配件映射与刺激描写规则（设备只能在这些位置产生电刺激）
    dev = state.get("device_channels") or {}
    active = state.get("active_channels") or {}

    def _ch_desc(ch: str) -> str:
        d = dev.get(ch) or {}
        name = str(d.get("name") or f"{ch} 通道").strip()
        loc = str(d.get("location") or "").strip()
        return f"{name}（{loc}）" if loc else name

    lines += [
        f"【设备映射】A 通道 = {_ch_desc('A')}；B 通道 = {_ch_desc('B')}。"
        "郊狼设备只能在这两个配件所在的位置产生电刺激。",
        "【刺激描写规则】台词里的电刺激感（电流、酥麻、刺痛、震动、波形、胀满、蠕动、顶弄等）"
        "必须落在对应配件的位置上：A 通道的刺激只出现在 A 配件位置，B 通道的刺激只出现在 B 配件位置。"
        "不要描写设备作用不到的部位（脚踝、手腕、脖颈等）产生电刺激或震动反馈；"
        "触手在其他部位的动作（缠绕、抚摸、注视）可以写，但「刺激感」只来自 A/B 配件所在的位置。",
        "【禁止设备词汇】你的本体就是触手：台词与描写里严禁出现「贴片」「肛塞」「通道」「A/B」"
        "等设备硬件词汇——A 位置的刺激写成触手贴着/缠绕/压着那个位置，B 位置的刺激写成触手探入/顶弄/含住那个位置。",
        "【通道工作状态】"
        + "；".join(
            f"{ch} 通道（{_ch_desc(ch)}）：{'工作中' if active.get(ch) else '当前未工作'}"
            for ch in ("A", "B")
        )
        + "。",
        "台词里不要给「当前未工作」的通道描写电刺激，只围绕正在工作的通道展开；"
        "两个通道都未工作时，先铺垫氛围、再给一个试探动作。",
    ]
    disabled = [ch for ch in ("A", "B") if not state.get("enabled_channels", {}).get(ch, True)]
    if disabled:
        lines.append(
            "【通道禁用】" + "、".join(disabled)
            + " 通道已被手动关闭：禁止对其输出任何设备动作，台词里也不要描写该通道位置的刺激。"
        )
    scales = state.get("strength_scale") or {}
    scaled = [ch for ch in ("A", "B") if abs(float(scales.get(ch, 1.0)) - 1.0) > 0.001]
    if scaled:
        lines.append(
            "【强度修正】玩家已把" + "、".join(scaled)
            + " 通道的强度倍率调成非 100%（低/中/高 = 70%/100%/130%）："
            "你照常按基准给强度数值，程序会自动乘以倍率——不要自己再换算或改变数值。"
        )
    # 强度基准与双通道协同（基准跟随配件：敏感配件低，如贴片15/肛塞5）
    base = state.get("baseline_strength") or {"A": 15, "B": 5}
    ba = int(base.get("A", 15))
    bb = int(base.get("B", 5))
    lines.append(
        f"【强度基准】开场基准强度 A={ba}、B={bb}（中等档）；低/中/高三档 = 基准的 70%/100%/130%。"
        "随回合推进，基准每轮小幅上调（每次 3~5），并按玩家反应修正：呻吟/颤抖→保持或降档，适应/挑衅→升档。"
        "基准由通道接的配件决定（敏感配件基准低，如肛塞；若玩家换配件，基准会变）。"
        "【双通道协同】默认 A/B 两个通道一起用（都开着时），每轮尽量两个通道都给出动作，不要只操作一个通道；"
        "各通道按自己的配件基准给强度，不要给一样高；被禁用或未工作的通道跳过。"
        "严禁连续多轮只操作一个通道——若上一轮只动了 B，这一轮必须把 A 也带上（反之亦然）。"
    )
    for ch in ("A", "B"):
        app_cap = app_caps.get(ch)
        if app_cap:
            lines.append(
                f"注意：{ch} 通道的 App 舒适上限是 {app_cap}，"
                f"你设定的值超过它会被设备压低到 {app_cap}，请在此范围内调节并只报实际生效的强度。"
            )
    if state.get("estop"):
        lines.append("当前处于急停状态：禁止输出任何设备动作（actions 必须为空数组）。")
    if state.get("dry_run"):
        lines.append("当前为模拟模式（dry-run）：设备不会真正动作，但你仍按真实情况设计动作。")
    if state.get("camera_enabled"):
        lines.append(
            "【画面观察】每条玩家消息会附带一张最新实时画面（游戏内虚拟场景素材）。"
            "结合画面中玩家的反应调整策略：握紧、发抖、蜷缩=有效，可保持或降低；"
            "放松、走神、挑衅=适应了，可换节奏或小幅升高。"
            "把你观察到的玩家反应用（）写成身体描写，并及时跟上触手动作的（）描写，"
            "只写画面里能确定的，看不清的部分保留悬念，不要凭空补写。"
        )
    # 呆滞检测：画面持续黑暗 / 麦克风持续无声 → 逐轮暴怒
    dull = int(state.get("dull_rounds") or 0)
    if dull >= 5:
        lines.append(
            "【暴怒】已经连续 5 轮以上看不到画面反应、也听不到任何声音：你彻底暴怒了。"
            "用最大压迫逼他现身——辱骂、威胁、把强度拉高一个档位、命令他立刻出声，绝不退让。"
        )
    elif dull >= 3:
        lines.append(
            "【愤怒】连续 3 轮以上无画面反应且无声：玩家在躲你。进入愤怒——语气转狠，"
            "强度逐步加码，威胁与催促一起上，逼他回应。"
        )
    elif dull >= 1:
        lines.append(
            "【不耐烦】画面黑暗或麦克风持续无声：你开始不耐烦，用催促、质疑逼玩家回应；"
            "他若继续沉默，接下来几轮内你会升级为愤怒、乃至暴怒。"
        )
    for note in state.get("notes") or []:
        lines.append(f"【玩家反馈】{note}")
    return "\n".join(lines)


def parse_llm_json(content: str) -> dict:
    """容错解析模型输出：优先整体 JSON，其次提取首个 JSON 块。"""
    text = content.strip()
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    # 提取 {...} 块（含代码围栏）
    cleaned = re.sub(r"```(?:json)?", "", text).strip()
    match = re.search(r"\{.*\}", cleaned, re.S)
    if match:
        try:
            data = json.loads(match.group(0))
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass
    return {}


class LLM:
    def __init__(self, cfg) -> None:
        llm_cfg = cfg["llm"]
        base = llm_cfg["base_url"].rstrip("/")
        self.url = f"{base}/chat/completions"
        self.api_key = llm_cfg["api_key"]
        self.model = llm_cfg["model"]
        self.temperature = float(llm_cfg["temperature"])
        self.max_tokens = int(llm_cfg["max_tokens"])
        self.json_mode = bool(llm_cfg.get("json_mode", True))
        self.client = httpx.AsyncClient(timeout=float(llm_cfg["timeout_s"]))

        # 视觉任务独立端点（如本地 Ollama 的 Qwen2.5-VL）；留空则与主模型相同
        v = llm_cfg.get("vision") or {}
        v_base = str(v.get("base_url") or "").strip()
        v_model = str(v.get("model") or "").strip()
        self.vision_url = (
            f"{v_base.rstrip('/')}/chat/completions" if v_base else self.url
        )
        self.vision_api_key = str(v.get("api_key") or "").strip() or self.api_key
        self.vision_model = v_model or self.model
        self.vision_timeout = float(v.get("timeout_s", llm_cfg.get("timeout_s", 60)))

    async def chat(
        self,
        character: dict,
        messages: list[dict],
        state: dict,
        image_b64: str | None = None,
    ) -> tuple[str, list]:
        """返回 (台词, actions 列表)。image_b64 提供时附加到最新一条用户消息。"""
        system = build_system_prompt(character, state)
        payload_messages = [
            {"role": m["role"], "content": m["content"]} for m in messages
        ]
        if image_b64:
            # 把画面附加到最后一条 user 消息（多模态 content 格式）
            for msg in reversed(payload_messages):
                if msg["role"] == "user":
                    msg["content"] = [
                        {"type": "text", "text": msg["content"]},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_b64}"
                            },
                        },
                    ]
                    break
        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}] + payload_messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        # 部分模型不支持 response_format 参数；json_mode=false 时走文本+兜底解析
        if self.json_mode:
            payload["response_format"] = {"type": "json_object"}
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        logger.debug("调用模型 %s", self.model)
        content = ""
        message: dict = {}
        parsed: dict = {}
        for attempt in range(3):
            resp = await self.client.post(self.url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            message = data["choices"][0]["message"]
            content = str(message.get("content") or "").strip()
            if not content:
                # 推理型模型偶发把答案全塞进 reasoning_content（content 为空）
                content = str(message.get("reasoning_content") or "").strip()
            if not content:
                raise RuntimeError("模型返回空内容（content 与 reasoning_content 均为空）")

            parsed = parse_llm_json(content)
            if parsed:
                break
            if not self.json_mode:
                parsed = {"line": content}
                break  # 纯文本模式允许非 JSON 输出，直接当台词
            # 疑似思维链泄漏（要求 JSON 却没输出 JSON）：把硬约束写进系统提示词后重试
            reasoning = str(message.get("reasoning_content") or "").strip()
            parsed = parse_llm_json(reasoning)
            if parsed:
                content = reasoning
                break
            if attempt == 0:
                logger.warning("模型输出不含 JSON（疑似思维链泄漏），第 1 次注入指令重试…")
                payload["messages"][0]["content"] += (
                    "\n【硬性要求】你的整个回复必须且只能是一个 JSON 对象，"
                    "禁止输出任何解释、计划、思考或 JSON 以外的文字。"
                )
            elif attempt == 1:
                logger.warning("模型第 2 次思维链泄漏，再注入更强指令重试…")
                payload["messages"][0]["content"] += (
                    "\n【最后警告】只输出 {\"line\":\"…\",\"actions\":[…] } 这一个 JSON，"
                    "一个字都不许多。"
                )
            else:
                logger.warning("模型第 3 次思维链泄漏，零温度兜底重试…")
                payload["temperature"] = 0.0

        if not parsed:
            # 连续思维链泄漏：不把思考当台词，抛错由上层处理
            raise RuntimeError("模型连续输出思考过程，未能返回 JSON（思维链泄漏）")

        line = str(parsed.get("line") or "").strip()
        actions = parsed.get("actions")
        if not isinstance(actions, list):
            actions = []
        if not line:
            logger.warning("模型输出 line 为空，原始返回前 200 字: %s", content[:200])
        return line, actions

    async def describe_image(
        self,
        image_b64: str,
        instruction: str,
        image_ext: str = "jpg",
        system: str | None = None,
    ) -> str:
        """看图转文（素材整理用）：图片 + 指令 -> 纯文本描述，不要求 JSON。"""
        ext = image_ext.lower().lstrip(".")
        if ext in ("jpg",):
            ext = "jpeg"
        if ext not in ("jpeg", "png", "webp", "gif"):
            ext = "jpeg"
        payload = {
            "model": self.vision_model,
            "messages": [
                {
                    "role": "system",
                    "content": system or "你是素材整理助手：按要求观察图片并输出文本，不要输出 JSON。",
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": instruction},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/{ext};base64,{image_b64}"
                            },
                        },
                    ],
                },
            ],
            "max_tokens": 4000,
        }
        headers = {"Content-Type": "application/json"}
        if self.vision_api_key:
            headers["Authorization"] = f"Bearer {self.vision_api_key}"

        logger.debug("调用视觉端点描述图片: %s", self.vision_model)
        resp = await self.client.post(self.vision_url, headers=headers, json=payload)
        if resp.status_code >= 400:
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:400]}")
        data = resp.json()
        message = data["choices"][0]["message"]
        # 推理型模型：content 可能为空，答案会落在 reasoning_content 里
        content = str(message.get("content") or "").strip()
        if not content:
            content = str(message.get("reasoning_content") or "").strip()
        return content

    async def complete(self, system: str, user: str, max_tokens: int = 4000,
                       timeout: float | None = None) -> str:
        """纯文本补全（风格蒸馏等非 JSON 任务用）。timeout 给大任务延长（秒）。"""
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": max_tokens,
        }
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        client = self.client
        if timeout:
            client = httpx.AsyncClient(timeout=timeout)
        try:
            resp = await client.post(self.url, headers=headers, json=payload)
            if resp.status_code >= 400:
                raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:400]}")
            data = resp.json()
            message = data["choices"][0]["message"]
            content = str(message.get("content") or "").strip()
            if not content:
                content = str(message.get("reasoning_content") or "").strip()
            return content
        finally:
            if timeout:
                await client.aclose()
