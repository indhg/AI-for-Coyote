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
from .device_ops import CHANNEL, DeviceOps
from .safety import SafetyManager

logger = logging.getLogger("ai-for-coyote.game")


class GameLoop:
    def __init__(self, cfg, llm, safety: SafetyManager, relay, camera=None, audio=None) -> None:
        self.cfg = cfg
        self.llm = llm
        self.safety = safety
        self.relay = relay
        self.camera = camera
        self.audio = audio
        self.ops = DeviceOps()

        self.history: list[dict] = []          # [{"role","content"}]
        self.notes: list[str] = []             # 反馈按钮等系统备注，注入下一轮
        self.keep = int(cfg["log"]["history_keep"])

        # 循环波形任务：channel -> (task, stop_event)
        self.loop_tasks: dict[str, asyncio.Task] = {}
        self.loop_events: dict[str, asyncio.Event] = {}

        # 当前播放的波形（按通道，供页面显示与 AI 上下文）
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
            silent = bool(self.audio.to_state().get("silent"))
        return dark or silent

    def _note_rage(self) -> None:
        """每轮开始前更新怒气值轮数。"""
        self.rage_triggered = self._sensor_rage()
        if self.rage_triggered:
            self.rage_rounds += 1
        else:
            self.rage_rounds = 0

    def build_state(self) -> dict:
        relay_state = self.relay.to_state()
        state = self.safety.to_state()
        state["relay_status"] = relay_state["status"]
        state["controller_id"] = relay_state["controller_id"]
        state["connected"] = relay_state["status"] == "paired"
        state["notes"] = list(self.notes)
        state["camera_enabled"] = bool(self.camera and self.camera.enabled)
        state["camera"] = self.camera.to_state() if self.camera else {}
        # 通道配件与工作状态（台词描写只落在设备位置 / 只写工作通道）
        state["device_channels"] = {
            ch: dict(self.cfg["device_channels"].get(ch) or {})
            for ch in ("A", "B")
        }
        pulse = self.safety.pulse_active()
        state["active_channels"] = {
            ch: bool(self.safety.current.get(ch))
            or bool(pulse.get(ch))
            or (ch in self.loop_tasks)
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
                    line = f"（模型调用失败：{exc}。请检查 API 配置与网络。）"
                actions = []
            self.turn_count += 1
            executed, dropped = await self.execute_actions(actions)
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
                line = f"（开场调用失败：{exc}）"
                actions = []
            self.turn_count += 1
            executed, dropped = await self.execute_actions(actions)
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
            if self.relay.to_state()["status"] != "paired":
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
            executed, dropped = await self.execute_actions(actions)
            await self._apply_channel_floor()
        finally:
            self.turn_busy = False
        self.history.append({"role": "assistant", "content": line})
        return {"line": line, "executed": executed, "dropped": dropped}

    # ---------- 自动运行（玩家不输入，AI 自主回合） ----------
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
                if not (self.relay.to_state()["status"] == "paired" or self.safety.dry_run):
                    continue  # 设备未配对不自动运行（用户设定：连接设备后才开始）
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
            executed, dropped = await self.execute_actions(actions)
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
        self, ch_name: str, client_id: str | None, slot_id: str | None,
        ready: bool, dry_run: bool,
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
            await self._start_pulse_loop(client_id, slot_id, CHANNEL[ch_name], ch_name, cmd)
        self.patterns[ch_name] = pattern
        self.safety.record(cmd)
        logger.info("自动挂载默认波形：%s 通道「%s」（强度需波形承载）", ch_name, pattern)

    async def _apply_channel_floor(self) -> None:
        """双通道保底：两轮后 A/B 都必须有波形且强度≠0；每 2 轮内强度与波形至少各调一次。"""
        if not (self.safety.enabled.get("A") and self.safety.enabled.get("B")):
            return
        if self.safety.estop_active:
            return
        client_id = self.relay.first_client_id()
        slot_id = self.relay.get_slot_id()
        ready = bool(client_id and slot_id)
        if not ready and not self.safety.dry_run:
            return
        for ch in ("A", "B"):
            base = int(self.cfg["device_channels"].get(ch, {}).get("baseline", 15 if ch == "A" else 5))
            wave_active = (ch in self.loop_tasks) or bool(self.safety.pulse_active().get(ch))
            strength = self.safety.current.get(ch, 0)
            fixed = False
            # 规则 1：前两轮结束后，强度必须非零且必须有波形
            if self.turn_count >= 2:
                if not wave_active:
                    await self._ensure_default_wave(ch, client_id, slot_id, ready, self.safety.dry_run)
                    self.last_wave[ch] = self.turn_count
                    fixed = True
                if strength <= 0:
                    cmd = {"kind": "hold", "channel": ch, "value": base}
                    self._scale_cmd(cmd)
                    if ready and not self.safety.dry_run:
                        await self._send_all(self._build_frames(cmd, client_id, slot_id))
                    self.safety.record(cmd)
                    self.last_strength[ch] = self.turn_count
                    fixed = True
            # 规则 2：每 2 轮内，强度与波形至少各调整一次
            if self.turn_count - self.last_strength.get(ch, 0) >= 2:
                delta = 5 if strength < self.safety.cap_for(ch) else -5
                cmd = {"kind": "add", "channel": ch, "delta": delta}
                self._scale_cmd(cmd)
                if ready and not self.safety.dry_run:
                    await self._send_all(self._build_frames(cmd, client_id, slot_id))
                self.safety.record(cmd)
                self.last_strength[ch] = self.turn_count
                fixed = True
            if self.turn_count - self.last_wave.get(ch, 0) >= 2:
                await self._ensure_default_wave(ch, client_id, slot_id, ready, self.safety.dry_run)
                self.last_wave[ch] = self.turn_count
                fixed = True
            if fixed:
                logger.info("通道保底：%s 通道强度/波形已自动补齐（第 %d 轮）", ch, self.turn_count)

    async def execute_actions(self, actions: list) -> tuple[list, list]:
        """校验并执行动作列表，返回 (已执行说明列表, 被拒绝说明列表)。"""
        executed, dropped = [], []
        if not isinstance(actions, list):
            return executed, dropped

        client_id = self.relay.first_client_id()
        slot_id = self.relay.get_slot_id()
        ready = bool(client_id and slot_id)
        dry_run = self.safety.dry_run

        for action in actions:
            if not isinstance(action, dict):
                dropped.append({"action": action, "reason": "动作必须是 JSON 对象"})
                continue
            ok, reason, cmd = self.safety.validate(action)
            if not ok:
                dropped.append({"action": action, "reason": reason})
                logger.warning("动作被安全层拒绝: %s -> %s", action, reason)
                continue

            if not ready and not dry_run:
                dropped.append({"action": action, "reason": "设备未连接（无 clientId/slotId）"})
                continue

            # 记录每通道最近一次强度/波形调整轮次（保底规则用）
            if cmd["kind"] in ("hold", "add", "temp") and cmd.get("channel") in ("A", "B"):
                self.last_strength[cmd["channel"]] = self.turn_count
            if cmd["kind"] in ("pulse", "pulse_hold") and cmd.get("channel") in ("A", "B"):
                self.last_wave[cmd["channel"]] = self.turn_count

            # 强度类动作必须有波形承载才有输出（DG-LAB 特性）：通道无波形时自动挂默认波形
            if cmd["kind"] in ("hold", "add", "temp") and cmd.get("channel") in ("A", "B"):
                ch_name = cmd["channel"]
                if ch_name not in self.loop_tasks and not self.safety.pulse_active().get(ch_name):
                    await self._ensure_default_wave(ch_name, client_id, slot_id, ready, dry_run)

            if cmd["kind"] == "pulse_hold":
                # 循环波形：程序周期性重发（不依赖 App 的 d=0），直到清除/急停
                sent = False
                if ready and not dry_run:
                    sent = await self._start_pulse_loop(
                        client_id, slot_id,
                        CHANNEL[cmd["channel"]], cmd["channel"], cmd,
                    )
                if cmd.get("channel") in ("A", "B"):
                    self.patterns[cmd["channel"]] = cmd.get("pattern")
                self.safety.record(cmd)
                label = self._describe(cmd)
                executed.append({"action": action, "reason": reason, "sent": sent, "label": label})
                logger.info("执行动作: %s（循环播放中）", label)
                continue

            if cmd["kind"] in ("clear", "stop"):
                # 清除/停止先取消该通道（或全部）的循环波形
                self._cancel_loops(None if cmd["kind"] == "stop" or cmd["channel"] is None else cmd["channel"])
                if cmd["kind"] == "stop" or cmd["channel"] is None:
                    self.patterns = {"A": None, "B": None}
                elif cmd["channel"] in ("A", "B"):
                    self.patterns[cmd["channel"]] = None

            if cmd["kind"] == "pulse" and cmd.get("channel") in ("A", "B"):
                self.patterns[cmd["channel"]] = cmd.get("pattern")

            frames = self._build_frames(cmd, client_id, slot_id)
            sent = False
            if ready and not dry_run:
                sent = all(await self._send_all(frames))
            self.safety.record(cmd)
            label = self._describe(cmd)
            executed.append({"action": action, "reason": reason, "sent": sent, "label": label})
            logger.info(
                "%s执行动作: %s（%s）",
                "DRY-RUN " if (dry_run or not ready) else "",
                label,
                "已发送" if sent else "模拟",
            )
        return executed, dropped

    def _build_frames(self, cmd: dict, client_id: str | None, slot_id: str | None) -> list[dict]:
        """内部命令 -> V4 服务器帧列表。client_id/slot_id 可能为 None（dry-run 时）。"""
        frames: list[dict] = []
        kind = cmd["kind"]
        if client_id is None or slot_id is None:
            return frames
        ch = CHANNEL.get(cmd.get("channel"))          # 数字通道（设备帧用）
        ch_name = cmd.get("channel")                   # 字母通道（safety 状态用）
        if kind == "temp":
            # 爆发：加差值到目标，到时自动归零
            delta = cmd["value"] - self.safety.current[ch_name]
            if delta:
                frames.append(self.ops.add_strength(client_id, slot_id, ch, delta))
            self._schedule_temp_revert(client_id, slot_id, ch, ch_name, cmd["duration_s"])
        elif kind == "hold":
            # 持续强度：加差值到目标（AddIntensity 是实测可靠的原语）
            delta = cmd["value"] - self.safety.current[ch_name]
            if delta:
                frames.append(self.ops.add_strength(client_id, slot_id, ch, delta))
        elif kind == "add":
            frames.append(self.ops.add_strength(client_id, slot_id, ch, cmd["delta"]))
        elif kind == "pulse":
            # 波形按帧消费（每帧 100ms），帧播完即停；循环补齐到请求的时长
            base = cmd["frames"]
            total = max(1, int(round(cmd["duration_s"] * 10)))
            tiled = (base * (total // len(base) + 1))[:total] if base else []
            frames.append(
                self.ops.pulse(
                    client_id, slot_id, ch, tiled,
                    int(cmd["duration_s"] * 1000), immediate=True,
                )
            )
        elif kind == "clear":
            frames.append(
                self.ops.clear(client_id, slot_id, None if cmd["channel"] is None else ch)
            )
            # 用可靠的 AddIntensity 负值归零，另发 reset 兜底
            if cmd["channel"] is None:
                for c in ("A", "B"):
                    if self.safety.current[c]:
                        frames.append(
                            self.ops.add_strength(
                                client_id, slot_id, CHANNEL[c], -self.safety.current[c]
                            )
                        )
                    frames.append(self.ops.reset_intensity(client_id, slot_id, CHANNEL[c]))
            else:
                if self.safety.current[ch_name]:
                    frames.append(
                        self.ops.add_strength(
                            client_id, slot_id, ch, -self.safety.current[ch_name]
                        )
                    )
                frames.append(self.ops.reset_intensity(client_id, slot_id, ch))
        elif kind == "stop":
            frames.append(self.ops.clear(client_id, slot_id))
            for c in ("A", "B"):
                if self.safety.current[c]:
                    frames.append(
                        self.ops.add_strength(
                            client_id, slot_id, CHANNEL[c], -self.safety.current[c]
                        )
                    )
                frames.append(self.ops.reset_intensity(client_id, slot_id, CHANNEL[c]))
        return frames

    def _schedule_temp_revert(
        self, client_id: str, slot_id: str, ch: int, ch_name: str, duration_s: float
    ) -> None:
        """爆发时长结束后自动归零（AddIntensity 负值 + reset 兜底）。"""

        async def revert() -> None:
            await asyncio.sleep(duration_s)
            if self.safety.estop_active:
                return
            value = self.safety.current[ch_name]
            frames = []
            if value:
                frames.append(
                    self.ops.add_strength(client_id, slot_id, ch, -value)
                )
            frames.append(self.ops.reset_intensity(client_id, slot_id, ch))
            sent = all(await self._send_all(frames))
            if sent:
                self.safety.record({"kind": "zero", "channel": ch_name})
                logger.info("爆发结束，%s 通道自动归零", ch_name)

        asyncio.create_task(revert())

    # ---------- 循环波形（无时间约束，直到清除/急停） ----------
    async def _start_pulse_loop(
        self, client_id: str, slot_id: str, ch: int, ch_name: str, cmd: dict
    ) -> bool:
        """分批下发波形实现无限循环，批间提前覆盖消除真空期。

        - 每批 = 波形自然周期的整数倍时长（尽量贴合循环边界）
        - 提前 loop_overlap_s 秒重发下一批（im=true 直接替换旧批），
          设备全程无「停止-重启」的空档
        - 不依赖 App 的 d=0（实测不可靠），只用普通波形帧
        """
        self._cancel_loops(ch_name)
        base = cmd["frames"]
        playback = self.cfg["playback"]
        frame_s = float(playback["frame_ms"]) / 1000.0
        natural = max(len(base) * frame_s, 0.1)
        batch_s = max(float(playback["loop_batch_s"]), natural)
        mult = max(1, round(batch_s / natural))
        batch_s = natural * mult
        overlap = min(float(playback["loop_overlap_s"]), batch_s * 0.5)
        total = max(1, int(round(batch_s * 10)))
        tiled = (base * (total // len(base) + 1))[:total] if base else []
        frame = self.ops.pulse(
            client_id, slot_id, ch, tiled, int(batch_s * 1000), immediate=True
        )
        wait_s = max(0.1, batch_s - overlap)

        stop_event = asyncio.Event()
        self.loop_events[ch_name] = stop_event

        async def worker() -> None:
            ok = await self._send_all([frame])
            if not ok:
                return
            logger.info(
                "%s 通道循环波形开始：%s（批次 %.1fs，提前 %.2fs 覆盖）",
                ch_name, cmd["pattern"], batch_s, overlap,
            )
            while not stop_event.is_set():
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=wait_s)
                    break
                except asyncio.TimeoutError:
                    pass
                if self.safety.estop_active:
                    break
                await self._send_all([frame])
            logger.info("%s 通道循环波形结束：%s", ch_name, cmd["pattern"])

        self.loop_tasks[ch_name] = asyncio.create_task(worker())
        return True

    def _cancel_loops(self, ch_name: str | None) -> None:
        """取消循环波形；ch_name=None 时取消全部。"""
        names = [ch_name] if ch_name else list(self.loop_events)
        for name in names:
            event = self.loop_events.pop(name, None)
            if event:
                event.set()
            task = self.loop_tasks.pop(name, None)
            if task:
                task.cancel()
        if ch_name and ch_name in self.safety.pulse_until:
            self.safety.pulse_until[ch_name] = 0.0

    async def _send_all(self, frames: list[dict]) -> list[bool]:
        return [await self.relay.send_frame(f) for f in frames]

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
        self._cancel_loops(None)  # 停掉所有循环波形
        self.patterns = {"A": None, "B": None}
        cmds = self.safety.estop()
        client_id = self.relay.first_client_id()
        slot_id = self.relay.get_slot_id()
        sent = False
        if client_id and slot_id and not self.safety.dry_run:
            frames: list[dict] = []
            for cmd in cmds:
                frames.extend(self._build_frames(cmd, client_id, slot_id))
            sent = all(await self._send_all(frames))
        return {"estop": True, "sent": sent}

    async def resume(self) -> dict:
        self.safety.resume()
        return {"estop": False}

    def on_client_disconnected(self) -> None:
        """APP 断开：停止所有循环波形并清零跟踪。"""
        self._cancel_loops(None)
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
