# -*- coding: utf-8 -*-
"""闭环决策：用户消息 -> 模型台词+指令 -> 安全校验 -> 执行 -> 记录反馈。

这是阶段 1 的核心闭环；阶段 3 的摄像头观察循环也复用同一执行通道。

强度模型（实测结论）：DG-LAB 4 App 对 SetTempIntensity(d=0) 支持不可靠，
AddIntensity（相对增减）是最可靠的原语。因此所有强度命令都换算成
「AddIntensity(目标 - 当前)」实现绝对控制，设备上报值即最终强度。
"""
import asyncio
import logging

from .config import reload_character
from .safety import SafetyManager
from .ui_en import describe_en, reason_en

logger = logging.getLogger("ai-for-coyote.game")


def _friendly_llm_error(exc: Exception) -> str:
    """把模型接口错误翻译成人话（中转站/配置常见坑）。"""
    err = str(exc)
    if "401" in err:
        return (
            "API Key 无效或未填：官方与中转站的密钥不通用，请确认 Base URL 与密钥配套；"
            "可在设置页点「测试连接」验证。"
        )
    if "400" in err:
        return "模型接口返回 400（参数不被支持，中转站常见）：请核对模型名，或关闭 JSON 模式后重试。"
    return f"模型调用失败：{err}。请检查 API 配置与网络。"


class GameLoop:
    def __init__(self, cfg, llm, safety: SafetyManager, backend, camera=None, audio=None) -> None:
        """backend: backend.device 的 DeviceBackend（默认 dglab_relay，零行为变化）。"""
        self.cfg = cfg
        self.llm = llm
        self.safety = safety
        self.backend = backend
        self.camera = camera
        self.audio = audio

        self.history: list[dict] = []          # [{"role","content"}]
        self.notes: list[str] = []             # 反馈按钮等系统备注，注入下一轮
        self.keep = int(cfg["log"]["history_keep"])

        # 当前播放的波形（按通道，供页面显示与 AI 上下文）
        # 循环波形的物理任务由 backend 维护；此处只保留展示/上下文用 patterns
        self.patterns: dict[str, str | None] = {"A": None, "B": None}

        # 自动观察循环（阶段 3 摄像头闭环）
        self.observe_task: asyncio.Task | None = None
        self.observe_stop = asyncio.Event()
        self.turn_busy = False                 # 防止用户回合与自动观察并发

        # 自动运行（AI 自主回合：观察→描写→动作→发言，玩家不用打字）
        self.autopilot = bool(cfg.get("autopilot", {}).get("enabled", False))
        self.autopilot_interval = float(cfg.get("autopilot", {}).get("interval_s", 12))
        self.autopilot_task: asyncio.Task | None = None
        self.autopilot_stop = asyncio.Event()
        self.on_ai_turn = None                 # 由 AppState 注入：把 AI 主动回合推送到页面

        # 双通道保底：轮次计数 + 每通道最近一次强度/波形调整轮次
        self.turn_count = 0
        self.last_strength = {"A": 0, "B": 0}
        self.last_wave = {"A": 0, "B": 0}

        # 怒气值检测：画面持续黑暗 / 麦克风持续无声 → 触手怒气逐轮上升
        self.rage_rounds = 0
        self.rage_triggered = False

    # ---------- 状态 ----------
    def _sensor_rage(self) -> bool:
        """画面持续黑暗 或 麦克风持续无声 → 怒气积累。"""
        dark = False
        if self.camera and self.camera.enabled:
            cs = self.camera.to_state()
            dark = bool(cs.get("has_frame")) and bool(cs.get("dark"))
        silent = False
        if self.audio and self.audio.enabled:
            ast = self.audio.to_state()
            # 麦克风开关关闭（未在监听）时不计无声，避免用户主动关麦却触发怒气
            silent = bool(ast.get("running")) and bool(ast.get("silent"))
        return dark or silent

    def _note_rage(self) -> None:
        """每轮开始前更新怒气值轮数。"""
        self.rage_triggered = self._sensor_rage()
        if self.rage_triggered:
            self.rage_rounds += 1
        else:
            self.rage_rounds = 0

    def build_state(self) -> dict:
        backend_state = self.backend.to_state()
        state = self.safety.to_state()
        state["relay_status"] = backend_state["status"]
        state["controller_id"] = backend_state["controller_id"]
        state["connected"] = backend_state["status"] in ("paired", "ready")
        state["notes"] = list(self.notes)
        state["camera_enabled"] = bool(self.camera and self.camera.enabled)
        state["camera"] = self.camera.to_state() if self.camera else {}
        # 通道配件与工作状态（台词描写只落在设备位置 / 只写工作通道）
        state["device_channels"] = {
            ch: dict(self.cfg["device_channels"].get(ch) or {})
            for ch in ("A", "B")
        }
        pulse = self.safety.pulse_active()
        loops = self.backend.loops_active()
        state["active_channels"] = {
            ch: bool(self.safety.current.get(ch))
            or bool(pulse.get(ch))
            or bool(loops.get(ch))
            for ch in ("A", "B")
        }
        state["patterns"] = dict(self.patterns)
        # 强度基准：跟随配件走（敏感配件基准低，如贴片15/肛塞5）
        state["baseline_strength"] = {}
        for ch in ("A", "B"):
            d = self.cfg["device_channels"].get(ch) or {}
            try:
                value = int(d.get("baseline", 15 if ch == "A" else 5))
            except (TypeError, ValueError):
                value = 15 if ch == "A" else 5
            state["baseline_strength"][ch] = max(0, min(100, value))
        state["rage_rounds"] = self.rage_rounds + int(self.cfg["character"].get("rage_baseline") or 0)
        state["rage_triggered"] = self.rage_triggered
        # 角色与风格版本（多角色两级：角色 → 风格档），页面切换用
        state["role"] = str(self.cfg["character"].get("role") or "触手")
        state["role_title"] = str(self.cfg["character"].get("role_title") or "主人")
        state["roles"] = list(self.cfg["character"].get("roles") or [])
        state["profile"] = str(self.cfg["character"].get("profile") or "纯爱")
        state["profiles"] = list(self.cfg["character"].get("profiles") or ["纯爱"])
        state["profile_available"] = dict(self.cfg["character"].get("profile_available") or {})
        state["profile_level"] = str(self.cfg["character"].get("profile_level") or "中")
        state["autopilot"] = bool(self.autopilot)
        state["autopilot_interval_s"] = self.autopilot_interval
        return state

    # ---------- 用户回合 ----------
    def clear_history(self) -> None:
        """清空对话历史（模型上下文；页面消息记录由前端同步清）。"""
        self.history.clear()
        logger.info("对话历史已清空")

    async def handle_user_message(self, text: str) -> dict:
        text = (text or "").strip()
        if not text:
            return {"line": "", "executed": [], "dropped": []}
        reload_character(self.cfg)  # 角色设定热加载：改完保存，下一条消息生效

        self.history.append({"role": "user", "content": text})
        self.history = self.history[-self.keep:]

        self.turn_busy = True
        try:
            self._note_rage()
            state = self.build_state()
            error = None
            try:
                line, actions = await self.llm.chat(
                    self.cfg["character"], self.history, state,
                    image_b64=self._latest_image(),
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception("模型调用失败")
                error = str(exc)
                if "思维链泄漏" in error or "思维链" in error:
                    line = "（模型走神了：连续输出思考过程已被拦截。把刚才的话再发一次就好。）"
                else:
                    line = f"（{_friendly_llm_error(exc)}）"
                actions = []
            self.turn_count += 1
            executed, dropped = await self.execute_actions(actions, apply_scale=True)
            await self._apply_channel_floor()
        finally:
            self.turn_busy = False

        self.history.append({"role": "assistant", "content": line})
        return {"line": line, "executed": executed, "dropped": dropped, "error": error}

    # ---------- 画面辅助 ----------
    def _latest_image(self) -> str | None:
        """取摄像头最新帧（启用时）。"""
        if self.camera and self.camera.enabled and self.camera.has_frame():
            return self.camera.base64()
        return None

    # ---------- 主动开场（配对成功后 AI 自动开口） ----------
    async def auto_open(self) -> dict:
        """场景开始：AI 主动开口挑逗并给出第一个轻微试探。"""
        reload_character(self.cfg)
        self._note_rage()
        state = self.build_state()
        prompt_msg = {
            "role": "user",
            "content": (
                "（系统提示：场景开始了，玩家刚进入你的领地。"
                "请主动开口挑逗他，并给出第一个轻微试探：低强度 + 一个持续波形（pulse_hold），"
                "不要只调强度不给波形。不要等待玩家先说话。）"
            ),
        }
        self.history.append(prompt_msg)
        self.history = self.history[-self.keep:]
        error = None
        self.turn_busy = True
        try:
            try:
                line, actions = await self.llm.chat(
                    self.cfg["character"], self.history, state,
                    image_b64=self._latest_image(),
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception("开场模型调用失败")
                error = str(exc)
                line = f"（开场调用失败：{_friendly_llm_error(exc)}）"
                actions = []
            self.turn_count += 1
            executed, dropped = await self.execute_actions(actions, apply_scale=True)
            await self._apply_channel_floor()
        finally:
            self.turn_busy = False
        self.history.append({"role": "assistant", "content": line})
        return {
            "line": line,
            "executed": executed,
            "dropped": dropped,
            "error": error,
        }

    # ---------- 自动观察循环（阶段 3：AI 看图 → 调整策略） ----------
    def start_observe_loop(self) -> None:
        cfg = self.cfg["camera"]
        if (
            self.observe_task
            or not self.camera
            or not self.camera.enabled
            or not bool(cfg.get("auto_observe", True))
        ):
            return
        interval = float(cfg.get("observe_interval_s", 10))
        self.observe_stop = asyncio.Event()
        self.observe_task = asyncio.create_task(self._observe_loop(interval))
        logger.info("自动观察循环启动：每 %ss 看一次画面", interval)

    def stop_observe_loop(self) -> None:
        self.observe_stop.set()
        if self.observe_task:
            self.observe_task.cancel()
            self.observe_task = None

    async def _observe_loop(self, interval: float) -> None:
        while not self.observe_stop.is_set():
            try:
                await asyncio.wait_for(self.observe_stop.wait(), timeout=interval)
                break
            except asyncio.TimeoutError:
                pass
            if self.safety.estop_active or self.turn_busy:
                continue
            if self.backend.to_state()["status"] not in ("paired", "ready"):
                continue
            if not (self.camera and self.camera.has_frame()):
                continue
            result = await self._auto_observe_turn()
            if result and self.on_ai_turn:
                try:
                    await self.on_ai_turn(result)
                except Exception:  # noqa: BLE001
                    logger.exception("自动观察回合推送失败")

    async def _auto_observe_turn(self) -> dict | None:
        """观察最新画面，决定是否调整，并把台词推给页面（由调用方广播）。"""
        reload_character(self.cfg)
        self._note_rage()
        state = self.build_state()
        prompt_msg = {
            "role": "user",
            "content": (
                "（系统提示：观察最新画面中玩家的反应。"
                "把你观察到的玩家实时反应用（）写成身体描写，"
                "把你此刻正在做的或刚调整的触手动作也用（）写，"
                "最后说一句台词接住他的状态。不要询问玩家，保持角色。）"
            ),
        }
        self.history.append(prompt_msg)
        self.history = self.history[-self.keep:]
        self.turn_busy = True
        try:
            try:
                line, actions = await self.llm.chat(
                    self.cfg["character"], self.history, state,
                    image_b64=self._latest_image(),
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception("自动观察模型调用失败")
                return None
            self.turn_count += 1
            executed, dropped = await self.execute_actions(actions, apply_scale=True)
            await self._apply_channel_floor()
        finally:
            self.turn_busy = False
        self.history.append({"role": "assistant", "content": line})
        return {"line": line, "executed": executed, "dropped": dropped}

    # ---------- 自动运行（玩家不输入，AI 自主回合） ----------
    def set_autopilot_interval(self, interval_s: float) -> float:
        """更新自动运行间隔；下一轮等待使用新值，不重启循环任务。"""
        self.autopilot_interval = max(5.0, min(30.0, float(interval_s)))
        return self.autopilot_interval

    def set_autopilot(self, enabled: bool) -> None:
        """开启/关闭自动运行：AI 每 interval_s 秒自主观察、描写、调整设备并发言。"""
        self.autopilot = bool(enabled)
        if self.autopilot and (self.autopilot_task is None or self.autopilot_task.done()):
            self.autopilot_stop = asyncio.Event()
            self.autopilot_task = asyncio.create_task(self._autopilot_loop())
            logger.info("自动运行已开启：每 %.1fs 一个自主回合", self.autopilot_interval)
        elif not self.autopilot:
            self.autopilot_stop.set()
            if self.autopilot_task:
                self.autopilot_task.cancel()
                self.autopilot_task = None
            logger.info("自动运行已停止")

    async def _autopilot_loop(self) -> None:
        while not self.autopilot_stop.is_set():
            try:
                try:
                    await asyncio.wait_for(self.autopilot_stop.wait(), timeout=self.autopilot_interval)
                    break
                except asyncio.TimeoutError:
                    pass
                if self.safety.estop_active or self.turn_busy:
                    continue
                if not (self.backend.ready() or self.safety.dry_run):
                    continue  # 设备未连接不自动运行（用户设定：连接设备后才开始）
                await self._autopilot_turn()
            except Exception:  # noqa: BLE001
                # 任何异常都不能杀死循环任务（曾因此静默死亡导致 AI 一直不说话）
                logger.exception("自动运行循环异常，跳过本轮继续")

    async def _autopilot_turn(self) -> dict | None:
        reload_character(self.cfg)
        self._note_rage()
        state = self.build_state()
        has_ai = any(m["role"] == "assistant" for m in self.history)
        prompt_msg = {
            "role": "user",
            "content": (
                "（系统提示：自动回合。观察当前画面与玩家状态（有画面/麦克风信号就写真实观察，"
                "没有就推进场景），按「玩家反应（）→触手动作（）→发言」写一段，"
                "并给出合适的设备动作（至少一个波形 + 强度组合，不要只调强度）。"
                "画面看不清的部分保留悬念。保持角色，不要询问玩家。）"
                if has_ai else
                "（系统提示：场景开始了，玩家刚进入你的领地。"
                "请主动开口挑逗他，并给出第一个轻微试探：低强度 + 一个持续波形（pulse_hold），"
                "不要只调强度不给波形。不要等待玩家先说话。）"
            ),
        }
        self.history.append(prompt_msg)
        self.history = self.history[-self.keep:]
        self.turn_busy = True
        try:
            try:
                line, actions = await self.llm.chat(
                    self.cfg["character"], self.history, state,
                    image_b64=self._latest_image(),
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception("自动回合模型调用失败: %s", exc)
                return None
            self.turn_count += 1
            executed, dropped = await self.execute_actions(actions, apply_scale=True)
            await self._apply_channel_floor()
        finally:
            self.turn_busy = False
        self.history.append({"role": "assistant", "content": line})
        logger.info("自动回合台词: %s", line)
        result = {"line": line, "executed": executed, "dropped": dropped}
        if self.on_ai_turn:
            try:
                await self.on_ai_turn(result)
            except Exception:  # noqa: BLE001
                logger.exception("自动回合推送失败")
        return result

    # ---------- 动作执行（AI 与手动共用） ----------
    async def _ensure_default_wave(
        self, ch_name: str, ready: bool, dry_run: bool,
    ) -> None:
        """给通道挂默认持续波形（强度没有波形承载时设备无输出）。"""
        pattern = str(self.cfg["ui"].get("default_wave", "呼吸") or "呼吸")
        meta = self.safety.presets.get(pattern)
        if not meta and self.safety.presets:
            pattern = next(iter(self.safety.presets))
            meta = self.safety.presets[pattern]
        if not meta:
            return
        cmd = {
            "kind": "pulse_hold", "channel": ch_name, "pattern": pattern,
            "wave_key": meta["waveform"], "frames": meta["frames"],
        }
        if ready and not dry_run:
            await self.backend.start_pulse_hold(ch_name, cmd)
        self.patterns[ch_name] = pattern
        self.safety.record(cmd)
        logger.info("自动挂载默认波形：%s 通道「%s」（强度需波形承载）", ch_name, pattern)

    async def _apply_channel_floor(self) -> None:
        """双通道保底：两轮后 A/B 都必须有波形且强度≠0；每 2 轮内强度与波形至少各调一次。"""
        if not (self.safety.enabled.get("A") and self.safety.enabled.get("B")):
            return
        if self.safety.estop_active:
            return
        ready = self.backend.ready()
        if not ready and not self.safety.dry_run:
            return
        for ch in ("A", "B"):
            base = int(self.cfg["device_channels"].get(ch, {}).get("baseline", 15 if ch == "A" else 5))
            wave_active = self.backend.loops_active().get(ch) or bool(self.safety.pulse_active().get(ch))
            strength = self.safety.current.get(ch, 0)
            fixed = False
            # 规则 1：前两轮结束后，强度必须非零且必须有波形
            if self.turn_count >= 2:
                if not wave_active:
                    await self._ensure_default_wave(ch, ready, self.safety.dry_run)
                    self.last_wave[ch] = self.turn_count
                    fixed = True
                if strength <= 0:
                    cmd = {"kind": "hold", "channel": ch, "value": base}
                    self._scale_cmd(cmd)
                    if ready and not self.safety.dry_run:
                        await self.backend.apply(cmd)
                    self.safety.record(cmd)
                    self.last_strength[ch] = self.turn_count
                    fixed = True
            # 规则 2：每 2 轮内，强度与波形至少各调整一次
            if self.turn_count - self.last_strength.get(ch, 0) >= 2:
                delta = 5 if strength < self.safety.cap_for(ch) else -5
                cmd = {"kind": "add", "channel": ch, "delta": delta}
                self._scale_cmd(cmd)
                if ready and not self.safety.dry_run:
                    await self.backend.apply(cmd)
                self.safety.record(cmd)
                self.last_strength[ch] = self.turn_count
                fixed = True
            if self.turn_count - self.last_wave.get(ch, 0) >= 2:
                await self._ensure_default_wave(ch, ready, self.safety.dry_run)
                self.last_wave[ch] = self.turn_count
                fixed = True
            if fixed:
                logger.info("通道保底：%s 通道强度/波形已自动补齐（第 %d 轮）", ch, self.turn_count)

    def _scale_cmd(self, cmd: dict) -> None:
        """按强度档倍率修正强度动作（最终强度 = AI 设定值 × 档位倍率；手动操作不乘）。

        只作用于 hold/add/temp 三类强度动作；倍率为 1.0 时跳过；结果再钳到该通道上限。
        """
        ch = cmd.get("channel")
        if ch not in ("A", "B") or cmd.get("kind") not in ("hold", "add", "temp"):
            return
        scale = self.safety.scale.get(ch, 1.0)
        if scale == 1.0:
            return
        cap = self.safety.cap_for(ch)
        try:
            if cmd["kind"] == "add":
                delta = round(int(cmd.get("delta", 0)) * scale)
                cmd["value"] = max(0, min(cap, self.safety.current.get(ch, 0) + delta))
            else:
                cmd["value"] = max(0, min(cap, round(int(cmd.get("value", 0)) * scale)))
        except (TypeError, ValueError):
            return

    async def execute_actions(self, actions: list, apply_scale: bool = False) -> tuple[list, list]:
        """校验并执行动作列表，返回 (已执行说明列表, 被拒绝说明列表)。

        apply_scale=True 时（AI 回合），强度动作按玩家选择的强度档倍率（轻/中/重）修正；
        手动操作（apply_scale=False）保持原值。
        """
        executed, dropped = [], []
        if not isinstance(actions, list):
            return executed, dropped

        # EN 模式：把发给页面的执行说明/拒绝原因换成英文（T051 §1.5/§4.2）
        en = str((self.cfg.get("character") or {}).get("lang") or "zh") == "en"

        ready = self.backend.ready()
        dry_run = self.safety.dry_run

        for action in actions:
            if not isinstance(action, dict):
                dropped.append(
                    {
                        "action": action,
                        "reason": (
                            reason_en("动作必须是 JSON 对象") if en else "动作必须是 JSON 对象"
                        ),
                    }
                )
                continue
            ok, reason, cmd = self.safety.validate(action)
            if not ok:
                if en:
                    reason = reason_en(reason)
                dropped.append({"action": action, "reason": reason})
                logger.warning("动作被安全层拒绝: %s -> %s", action, reason)
                continue

            if not ready and not dry_run:
                dropped.append(
                    {
                        "action": action,
                        "reason": (
                            reason_en("设备未连接（无 clientId/slotId）")
                            if en
                            else "设备未连接（无 clientId/slotId）"
                        ),
                    }
                )
                continue

            # AI 回合：强度动作按玩家强度档倍率修正（手动操作已在调用处传 apply_scale=False）
            if apply_scale:
                self._scale_cmd(cmd)

            # 记录每通道最近一次强度/波形调整轮次（保底规则用）
            if cmd["kind"] in ("hold", "add", "temp") and cmd.get("channel") in ("A", "B"):
                self.last_strength[cmd["channel"]] = self.turn_count
            if cmd["kind"] in ("pulse", "pulse_hold") and cmd.get("channel") in ("A", "B"):
                self.last_wave[cmd["channel"]] = self.turn_count

            # 强度类动作必须有波形承载才有输出（DG-LAB 特性）：通道无波形时自动挂默认波形
            if cmd["kind"] in ("hold", "add", "temp") and cmd.get("channel") in ("A", "B"):
                ch_name = cmd["channel"]
                if not self.backend.loops_active().get(ch_name) and not self.safety.pulse_active().get(ch_name):
                    await self._ensure_default_wave(ch_name, ready, dry_run)

            if cmd["kind"] == "pulse_hold":
                # 循环波形：由 backend 内部周期性重发，直到清除/急停
                sent = False
                if ready and not dry_run:
                    sent = await self.backend.start_pulse_hold(cmd["channel"], cmd)
                if cmd.get("channel") in ("A", "B"):
                    self.patterns[cmd["channel"]] = cmd.get("pattern")
                self.safety.record(cmd)
                label = describe_en(cmd) if en else self._describe(cmd)
                executed.append({"action": action, "reason": reason, "sent": sent, "label": label})
                logger.info("执行动作: %s（循环播放中）", label)
                continue

            if cmd["kind"] in ("clear", "stop"):
                # 清除/停止先取消该通道（或全部）的循环波形
                self.backend.stop_pulse_hold(
                    None if cmd["kind"] == "stop" or cmd["channel"] is None else cmd["channel"]
                )
                if cmd["kind"] == "stop" or cmd["channel"] is None:
                    self.patterns = {"A": None, "B": None}
                elif cmd["channel"] in ("A", "B"):
                    self.patterns[cmd["channel"]] = None

            if cmd["kind"] == "pulse" and cmd.get("channel") in ("A", "B"):
                self.patterns[cmd["channel"]] = cmd.get("pattern")

            sent = False
            if ready and not dry_run:
                sent = await self.backend.apply(cmd)
            self.safety.record(cmd)
            label = describe_en(cmd) if en else self._describe(cmd)
            executed.append({"action": action, "reason": reason, "sent": sent, "label": label})
            logger.info(
                "%s执行动作: %s（%s）",
                "DRY-RUN " if (dry_run or not ready) else "",
                label,
                "已发送" if sent else "模拟",
            )
        return executed, dropped

    @staticmethod
    def _describe(cmd: dict) -> str:
        kind = cmd["kind"]
        ch = cmd.get("channel")
        if kind == "temp":
            return f"{ch} 爆发 {cmd['value']} × {cmd['duration_s']:.1f}s（结束归零）"
        if kind == "hold":
            return f"{ch} 持续强度 {cmd['value']}（保持）"
        if kind == "add":
            return f"{ch} 增减 {cmd['delta']:+d}"
        if kind == "pulse":
            return f"{ch} 波形「{cmd['pattern']}」× {cmd['duration_s']:.1f}s"
        if kind == "pulse_hold":
            return f"{ch} 持续波形「{cmd['pattern']}」（循环）"
        if kind == "clear":
            return "清除全部" if ch is None else f"清除 {ch} 通道"
        return "急停清零"

    # ---------- 急停 / 恢复 ----------
    async def estop(self) -> dict:
        self.backend.stop_pulse_hold(None)  # 停掉所有循环波形
        self.patterns = {"A": None, "B": None}
        cmds = self.safety.estop()
        sent = False
        if self.backend.ready() and not self.safety.dry_run:
            results = [await self.backend.apply(cmd) for cmd in cmds]
            sent = all(results)
        return {"estop": True, "sent": sent}

    async def resume(self) -> dict:
        self.safety.resume()
        return {"estop": False}

    def on_client_disconnected(self) -> None:
        """设备断开：停止所有循环波形并清零跟踪。"""
        self.backend.stop_pulse_hold(None)
        self.patterns = {"A": None, "B": None}
        self.safety.record({"kind": "stop"})

    # ---------- 设备反馈 ----------
    async def handle_feedback(self, action: int, client_id: str) -> None:
        """APP 反馈按钮（custom.action 0-9）。"""
        self.add_note(f"玩家按下了反馈按钮 {action}")

    def add_note(self, note: str) -> None:
        """实时信号（反馈按钮/麦克风转写等）注入下一轮 AI 上下文。"""
        self.notes.append(note)
        self.notes = self.notes[-5:]
