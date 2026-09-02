# -*- coding: utf-8 -*-
"""AI 郊狼驯服师 —— 主程序入口（FastAPI）。

启动后：
- 后台连接 dglab-websocket-server v4 中继；
- Web 页面：聊天、手动控制、实时状态、急停、配对二维码、日志；
- 所有设备命令统一走 safety -> device_ops -> relay 链路。
"""
import asyncio
import contextlib
import io
import os
import re
import socket
import sys
import urllib.parse
from pathlib import Path

import httpx
import qrcode
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

from .audio import AudioManager
from .camera import Camera
from .update_check import UpdateChecker
from .config import (
    load_config,
    reload_character,
    save_autopilot_interval,
    save_character_runtime,
    save_device_channels,
)
from .game_loop import GameLoop
from .llm import LLM
from .logging_utils import setup_logging
from .device.factory import build_backend
from .safety import SafetyManager
from .dungeon.runtime import DungeonRuntime

# 打包（PyInstaller）后以 exe 所在目录为项目根；开发时以仓库根
if getattr(sys, "frozen", False):
    PROJECT_ROOT = Path(sys.executable).resolve().parent
else:
    PROJECT_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"


def _app_version() -> str:
    """版本号：打包时写入 version.txt；源码运行时显示 dev。"""
    f = PROJECT_ROOT / "version.txt"
    if f.exists():
        v = f.read_text(encoding="utf-8").strip().lstrip("\ufeff")
        if v:
            return v
    return "dev"


def get_lan_ip() -> str:
    """探测本机局域网 IP（用于配对二维码）。"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def get_local_ips() -> list[str]:
    """列出本机所有可用 IPv4（含自动探测结果），供网络自检。"""
    ips: set[str] = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith("127.") and not ip.startswith("169.254."):
                ips.add(ip)
    except OSError:
        pass
    ips.add(get_lan_ip())
    return sorted(ips)


def build_pair_url(cfg, lan_ip: str, controller_id: str) -> str:
    """生成 DG-LAB 4 APP Socket V4 配对链接（局域网或公网中继）。"""
    public_url = str(cfg["relay"].get("public_url") or "").strip()
    base = public_url if public_url else f"ws://{lan_ip}:9998"
    return "https://dungeon-lab.cn/s/?v=1&action=socket&url=" + urllib.parse.quote(
        f"{base}?tid={controller_id}", safe=""
    )


class AppState:
    """共享运行对象 + Web 广播。"""

    def __init__(self, cfg) -> None:
        self.cfg = cfg
        self.logger = setup_logging(cfg["log_dir"], cfg["log"]["level"])

        self.safety = SafetyManager(cfg)
        self.backend = build_backend(
            cfg, self.safety, on_event=self.on_relay_event, on_action=self.on_relay_action
        )
        self.backend.on_disconnect(self._on_backend_disconnect)
        # 测试模式（不连郊狼）：保存真实后端，切换时换回
        self._real_backend = self.backend
        self._sim_backend = None
        self._test_mode = False
        self._test_mode_lock = asyncio.Lock()
        self.llm = LLM(cfg)
        self.camera = Camera(cfg)
        self.audio = AudioManager(
            cfg, on_text=self.on_audio_text, on_moan=self.on_audio_moan
        )
        self.loop = GameLoop(cfg, self.llm, self.safety, self.backend, self.camera, self.audio)
        self.loop.on_ai_turn = self.broadcast_chat  # AI 主动回合推送到页面聊天区
        self.dungeon = DungeonRuntime(cfg, self.llm, self.safety, PROJECT_ROOT)
        # 地牢反馈真机发送接入同一后端（M3 遗留缺口：FeedbackExecutor 此前无 send 回调）
        if getattr(self.dungeon, "executor", None) is not None:
            self.dungeon.executor.send = self.backend.apply

        self.ws_clients: set[WebSocket] = set()
        self.tasks: list[asyncio.Task] = []
        self.auto_opened = False
        self.sensors_on = False
        self.sensor_watch_task: asyncio.Task | None = None
        self.layout: dict = {}  # 前端上报的三栏布局（监测/调试用）
        self.update = UpdateChecker(
            enabled=bool(self.cfg["app"].get("check_update", True)),
            url=self.cfg["app"].get("update_url", ""),
        )
        # 传感器运行时开关（不持久化；初始跟随 config.enabled）
        self.sensor_switches: dict[str, bool] = {
            "camera": bool(self.cfg["camera"].get("enabled", False)),
            "audio": bool(self.cfg["audio"].get("enabled", False)),
        }

    # ---------- 麦克风转写回调 ----------
    async def on_audio_text(self, text: str) -> None:
        self.loop.add_note(f"麦克风检测到玩家说：「{text}」")
        self.logger.info("麦克风信号已注入：%s", text)
        await self.broadcast()

    # ---------- 麦克风呻吟回调（无文字片段按电平分级） ----------
    async def on_audio_moan(self, kind: str, level: float) -> None:
        if kind == "high":
            self.loop.add_note(
                "麦克风检测到玩家发出较大的呻吟/惨叫（音量高）：应降低强度、安抚并关心，不要继续加码。"
            )
        else:
            self.loop.add_note(
                "麦克风检测到玩家发出普通呻吟/呜呜声（音量中等）：挑逗等级可逐渐增加，小幅加码。"
            )
        self.logger.info("麦克风呻吟信号注入：%s（%.3f）", kind, level)
        await self.broadcast()

    # ---------- 中继事件 ----------
    async def on_relay_event(self, event: str, payload: dict) -> None:
        if event == "slots_patch":
            # 取第一台设备的 props/slotState 同步给安全层
            client = self.backend.client_state()
            if client:
                self.safety.update_device_state(
                    client.get("props"), client.get("slotState")
                )
        elif event == "client_attached" and not self.auto_opened:
            # 首次配对成功：AI 主动开场（挑逗 + 第一个轻微试探）
            self.auto_opened = True
            asyncio.create_task(self._auto_open_and_broadcast())
        if event == "client_disconnected" and self.cfg["safety"]["auto_clear_on_disconnect"]:
            self.loop.on_client_disconnected()
            self.logger.warning("APP 断开，自动清零并停止循环波形")
        await self.broadcast()

    async def _on_backend_disconnect(self, payload: dict) -> None:
        """设备/链路断开（BLE notify 超时、中继断开等）：按配置自动清零。"""
        if self.cfg["safety"]["auto_clear_on_disconnect"]:
            self.loop.on_client_disconnected()
        self.logger.warning("设备后端断开，已按配置处理: %s", payload)
        await self.broadcast()

    async def _auto_open_and_broadcast(self) -> None:
        try:
            # 配对成功后缓 3 秒再开场，给玩家反应时间
            await asyncio.sleep(3)
            result = await self.loop.auto_open()
            await self.broadcast_chat(result)
            self.logger.info("AI 主动开场完成")
        except Exception as exc:  # noqa: BLE001
            self.logger.exception("主动开场失败: %s", exc)

    async def on_relay_action(self, action: int, client_id: str) -> None:
        await self.loop.handle_feedback(action, client_id)
        await self.broadcast()

    # ---------- 广播 ----------
    async def broadcast(self) -> None:
        state = self.build_state()
        dead = []
        for ws in list(self.ws_clients):
            try:
                await ws.send_json({"type": "state", "data": state})
            except Exception:  # noqa: BLE001
                dead.append(ws)
        for ws in dead:
            self.ws_clients.discard(ws)

    async def broadcast_chat(self, result: dict) -> None:
        """把 AI 主动生成的台词推送到页面聊天区。"""
        dead = []
        for ws in list(self.ws_clients):
            try:
                await ws.send_json({"type": "chat", **result})
            except Exception:  # noqa: BLE001
                dead.append(ws)
        for ws in dead:
            self.ws_clients.discard(ws)

    def build_state(self) -> dict:
        state = self.loop.build_state()
        state["sensors_on"] = self.sensors_on
        state["sensors"] = dict(self.sensor_switches)
        state["relay"] = self.backend.to_state()
        state["device_backend"] = self.backend.name
        state["test_mode"] = self._test_mode
        state["audio"] = self.audio.to_state()
        state["layout"] = dict(self.layout)
        state["update"] = self.update.to_state(_app_version())
        state["character"] = self.cfg["character"]["name"]
        state["lang"] = str(self.cfg["character"].get("lang") or "zh")
        state["en_available"] = bool(self.cfg["character"].get("en_available"))
        state["dungeon"] = self.dungeon.to_state()
        state["config_info"] = {
            "model": self.cfg["llm"]["model"],
            "character_file": str(self.cfg["character_file"]),
            "waveforms_file": str(PROJECT_ROOT / "config" / "waveforms.yaml"),
            "title": str(self.cfg["app"].get("title", "郊狼 · AI 驯服师")),
            "profile": str(self.cfg["character"].get("profile") or "调教"),
            "player_nick": str(self.cfg["character"].get("player_nick") or "小柳"),
            "version": _app_version(),
        }
        return state

    # ---------- 测试模式（不连郊狼，模拟设备全流程试跑） ----------
    def _sim_backend_instance(self):
        """懒创建模拟后端（测试模式用）。"""
        if self._sim_backend is None:
            from backend.device.sim_backend import SimulatedBackend

            self._sim_backend = SimulatedBackend()
        return self._sim_backend

    def _attach_backend(self, backend) -> None:
        """把某个后端挂到所有消费点上（loop / 地牢执行器 / 本对象状态）。"""
        self.backend = backend
        self.loop.backend = backend
        if getattr(self.dungeon, "executor", None) is not None:
            self.dungeon.executor.send = backend.apply

    async def set_test_mode(self, on: bool) -> dict:
        """开/关测试模式：开 = 换模拟后端 + 强制 dry-run + 假装配对成功；关 = 恢复真实中继。"""
        on = bool(on)
        # 串行化开关：连点/前后两次请求交叠时，避免 stop/start 与 backend 换绑交错执行
        async with self._test_mode_lock:
            if on == self._test_mode:
                return {"ok": True, "test_mode": self._test_mode}
            if on:
                await self._real_backend.stop()          # 停真实中继重连任务
                self._attach_backend(self._sim_backend_instance())
                self.safety.dry_run = True               # 全体标「模拟」+ AI 被告知 dry-run
                self._test_mode = True
                self.logger.info("已进入测试模式：模拟设备已配对，不发送真实命令")
                # 与真实配对一致：缓 3 秒让 AI 主动开场
                if not self.auto_opened:
                    self.auto_opened = True
                    asyncio.create_task(self._auto_open_and_broadcast())
            else:
                sim = self._sim_backend
                if sim is not None:
                    await sim.stop()
                self._attach_backend(self._real_backend)
                self.safety.dry_run = bool(self.cfg["app"].get("dry_run", True))
                self._test_mode = False
                # 清掉模拟态残留的强度/波形，避免退出后 UI 显示模拟数值（真实设备 slots_patch 覆盖前）
                self.loop.on_client_disconnected()
                self.logger.info("已退出测试模式，恢复真实设备配对")
                asyncio.create_task(self._real_backend.start())
            await self.broadcast()
            return {"ok": True, "test_mode": self._test_mode}

    # ---------- 传感器开关（跟随自动运行；浏览器断开超时自动关） ----------
    async def set_sensors(self, on: bool) -> None:
        """自动运行开启时启动「开关为开」的传感器，关闭时全部停止（config.enabled 为初始默认）。"""
        self.sensors_on = bool(on)
        if on:
            if self.sensor_switches.get("camera"):
                await self.camera.start()
            else:
                await self.camera.stop()
            if self.sensor_switches.get("audio"):
                await self.audio.start()
            else:
                await self.audio.stop()
        else:
            await self.camera.stop()
            await self.audio.stop()

    def _on_ws_clients_change(self) -> None:
        """有浏览器接入：重启传感器（自动运行开着时）；全断开：延迟关传感器。"""
        if self.ws_clients:
            if self.sensor_watch_task:
                self.sensor_watch_task.cancel()
                self.sensor_watch_task = None
            if self.loop.autopilot and not self.sensors_on:
                asyncio.create_task(self.set_sensors(True))
        elif self.sensor_watch_task is None:
            self.sensor_watch_task = asyncio.create_task(self._watch_sensors_idle())

    async def _watch_sensors_idle(self) -> None:
        timeout = float(self.cfg["app"].get("sensor_idle_timeout_s", 30))
        try:
            await asyncio.sleep(timeout)
        finally:
            self.sensor_watch_task = None
        if not self.ws_clients:
            self.logger.info("浏览器已断开 %.0fs，自动关闭摄像头/麦克风", timeout)
            await self.set_sensors(False)
            await self.broadcast()

    async def _sensor_watchdog(self) -> None:
        """看门狗：开关开着但传感器没在跑且有错误时，每 15s 自动重试启动（拔插设备自恢复）。"""
        while True:
            await asyncio.sleep(15)
            try:
                if not self.sensors_on:
                    continue
                cam_bad = (
                    self.sensor_switches.get("camera")
                    and not self.camera.has_frame()
                    and bool(self.camera.error)
                )
                mic_bad = (
                    self.sensor_switches.get("audio")
                    and not self.audio.to_state().get("running")
                )
                if cam_bad or mic_bad:
                    self.logger.info("传感器看门狗重试启动（摄像头=%s 麦克风=%s）", cam_bad, mic_bad)
                    await self.set_sensors(True)
                    await self.broadcast()
            except Exception:  # noqa: BLE001
                self.logger.exception("传感器看门狗异常")

    # ---------- 更新检测 ----------
    async def _update_loop(self) -> None:
        """启动查一次 + 每 6 小时静默复查；结果写进状态供顶栏徽章展示。"""
        while True:
            await self.update.check()
            await self.broadcast()
            await asyncio.sleep(6 * 3600)

    # ---------- 生命周期 ----------
    async def start_background(self) -> None:
        self.tasks.append(asyncio.create_task(self.backend.start()))
        self.tasks.append(asyncio.create_task(self._sensor_watchdog()))
        self.tasks.append(asyncio.create_task(self._update_loop()))
        # 配置里自动运行开着时，启动真正的循环任务（此前只置状态、不启动任务，
        # 导致重启后「假开真停」：AI 一直不说话）
        if self.loop.autopilot:
            self.loop.set_autopilot(True)
        # 自动运行开着也只在「已有浏览器接入」时才启动传感器；
        # 无浏览器时不占摄像头/麦克风，等页面连上后由 _on_ws_clients_change 再启动
        if self.loop.autopilot and self.ws_clients:
            await self.set_sensors(True)
        self.loop.start_observe_loop()

    async def shutdown(self) -> None:
        # 退出时急停（若配置了断开自动清零）
        self.loop.stop_observe_loop()
        self.loop.set_autopilot(False)
        await self.camera.stop()
        await self.audio.stop()
        if self.cfg["safety"]["auto_clear_on_disconnect"]:
            with contextlib.suppress(Exception):
                await self.loop.estop()
        with contextlib.suppress(Exception):
            await self.backend.stop()
        for task in self.tasks:
            task.cancel()


def make_app() -> FastAPI:
    cfg = load_config()
    state = AppState(cfg)
    app = FastAPI(title="AI Coyote Tamer")

    @app.on_event("startup")
    async def startup() -> None:
        await state.start_background()
        state.logger.info(
            "启动完成。Web: http://%s:%s  dry_run=%s",
            cfg["app"]["host"], cfg["app"]["port"], cfg["app"]["dry_run"],
        )

    @app.on_event("shutdown")
    async def shutdown() -> None:
        await state.shutdown()

    # ---------- 页面 ----------
    @app.get("/")
    async def index() -> Response:
        # 托管 React 前端构建产物；未构建时给出一句构建提示
        if (FRONTEND_DIST / "index.html").exists():
            return FileResponse(FRONTEND_DIST / "index.html")
        return Response(
            "前端尚未构建：请在 frontend\\ 目录执行 npm install && npm run build",
            media_type="text/plain; charset=utf-8",
        )

    @app.get("/index.html")
    async def index_html() -> RedirectResponse:
        """收藏夹/手输带 index.html 的地址时别 404，重定向回首页。"""
        return RedirectResponse("/")

    # React 构建产物的静态资源（存在时才挂载）
    if (FRONTEND_DIST / "assets").exists():
        app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/api/state")
    async def api_state() -> JSONResponse:
        return JSONResponse(state.build_state())

    @app.get("/api/qrcode.png")
    async def api_qrcode() -> Response:
        controller_id = state.backend.controller_id()
        if not controller_id:
            return Response(
                "设备未就绪：dglab 后端需中继已连接；coyote2_ble 后端无二维码（走 BLE 扫描）",
                status_code=503,
                media_type="text/plain",
            )
        lan_ip = cfg["relay"]["lan_ip"]
        if lan_ip == "auto":
            lan_ip = get_lan_ip()
        url = build_pair_url(cfg, lan_ip, controller_id)
        img = qrcode.make(url)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return Response(content=buf.getvalue(), media_type="image/png")

    @app.get("/api/pair_url")
    async def api_pair_url() -> JSONResponse:
        controller_id = state.backend.controller_id()
        if not controller_id:
            return JSONResponse({"error": "设备未就绪（dglab 中继未连接；coyote2_ble 无二维码）"}, status_code=503)
        lan_ip = cfg["relay"]["lan_ip"]
        if lan_ip == "auto":
            lan_ip = get_lan_ip()
        return JSONResponse({"url": build_pair_url(cfg, lan_ip, controller_id)})

    @app.get("/api/network")
    async def api_network() -> JSONResponse:
        """网络自检：本机 IP 列表 + 当前配对地址（dglab 后端用）。"""
        controller_id = state.backend.controller_id()
        lan_ip = cfg["relay"]["lan_ip"]
        if lan_ip == "auto":
            lan_ip = get_lan_ip()
        pair_url = (
            build_pair_url(cfg, lan_ip, controller_id) if controller_id else None
        )
        return JSONResponse(
            {
                "lan_ip": lan_ip,
                "all_ips": get_local_ips(),
                "pair_url": pair_url,
                "public_url": str(cfg["relay"].get("public_url") or ""),
                "relay_port": 9998,
                "hint": (
                    "手机浏览器打开 http://<电脑IP>:9998/ 若立即显示 "
                    "'WebSocket upgrade required' 说明链路通；超时说明被防火墙/热点隔离拦截。"
                ),
            }
        )

    # ---------- 控制 ----------
    @app.post("/api/chat")
    async def api_chat(body: dict) -> JSONResponse:
        result = await state.loop.handle_user_message(str(body.get("message", "")))
        await state.broadcast()
        return JSONResponse(result)

    @app.post("/api/estop")
    async def api_estop() -> JSONResponse:
        result = await state.loop.estop()
        await state.broadcast()
        return JSONResponse(result)

    @app.post("/api/resume")
    async def api_resume() -> JSONResponse:
        result = await state.loop.resume()
        await state.broadcast()
        return JSONResponse(result)

    @app.post("/api/manual")
    async def api_manual(body: dict) -> JSONResponse:
        """手动控制：与 AI 指令走完全相同的安全链路。"""
        if not isinstance(body, dict) or "op" not in body:
            return JSONResponse({"error": "缺少 op"}, status_code=400)
        executed, dropped = await state.loop.execute_actions([body])
        await state.broadcast()
        return JSONResponse({"executed": executed, "dropped": dropped})

    @app.post("/api/device/channels")
    async def api_device_channels(body: dict) -> JSONResponse:
        """通道配件设置：{A:{name,location}, B:{...}}，保存到 device_channels.yaml。"""
        try:
            save_device_channels(cfg, body)
        except ValueError as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        await state.broadcast()
        return JSONResponse({"ok": True, "device_channels": cfg["device_channels"]})

    @app.post("/api/device/channels/enabled")
    async def api_device_channel_enabled(body: dict) -> JSONResponse:
        """手动开关通道：{channel:"A", enabled:false}。关闭的通道拒绝一切动作并清零。"""
        ch = str(body.get("channel") or "").strip().upper()
        if ch not in ("A", "B"):
            return JSONResponse({"error": "channel 只能是 A 或 B"}, status_code=400)
        enabled = bool(body.get("enabled"))
        state.safety.set_channel_enabled(ch, enabled)
        try:
            save_device_channels(cfg, {ch: {"enabled": enabled}})
        except ValueError as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        await state.broadcast()
        return JSONResponse({"ok": True, "enabled_channels": state.safety.enabled})

    @app.post("/api/sensors")
    async def api_sensors(body: dict) -> JSONResponse:
        """运行时单独开关摄像头/麦克风：{camera: bool, audio: bool}（可只传一项；不持久化）。"""
        changed = False
        for key in ("camera", "audio"):
            if key in body and isinstance(body[key], bool):
                if state.sensor_switches.get(key) != body[key]:
                    state.sensor_switches[key] = body[key]
                    changed = True
        if changed:
            # 传感器正在运行时按最新开关重新对齐（关掉的立即停）
            if state.sensors_on:
                await state.set_sensors(True)
            await state.broadcast()
        return JSONResponse({"ok": True, "sensors": state.sensor_switches})

    @app.post("/api/history/clear")
    async def api_history_clear(body: dict) -> JSONResponse:
        """清空对话历史（模型上下文 + 页面记录由前端同步清）。"""
        state.loop.clear_history()
        return JSONResponse({"ok": True})

    @app.post("/api/layout")
    async def api_layout(body: dict) -> JSONResponse:
        """前端上报三栏布局（调试/监测用）：{sidebar_w, control_w, inner_width, zoom}。"""
        try:
            state.layout = {
                "sidebar_w": float(body.get("sidebar_w", 0)),
                "control_w": float(body.get("control_w", 0)),
                "inner_width": float(body.get("inner_width", 0)),
                "zoom": float(body.get("zoom", 1.0)),
            }
        except (TypeError, ValueError):
            return JSONResponse({"error": "数值格式错误"}, status_code=400)
        return JSONResponse({"ok": True, "layout": state.layout})

    @app.post("/api/device/channels/cap")
    async def api_device_channel_cap(body: dict) -> JSONResponse:
        """调通道运行时强度上限（1~硬上限，不持久化）：{channel:"A", value:60}。"""
        ch = str(body.get("channel") or "").strip().upper()
        if ch not in ("A", "B"):
            return JSONResponse({"error": "channel 只能是 A 或 B"}, status_code=400)
        try:
            value = int(body.get("value", 100))
        except (TypeError, ValueError):
            return JSONResponse({"error": "value 必须是整数"}, status_code=400)
        v = state.safety.set_user_cap(ch, value)
        # 上限低于当前强度时，立即把设备强度降下来
        if state.safety.current[ch] > v:
            await state.loop.execute_actions(
                [{"op": "hold_strength", "channel": ch, "value": v}]
            )
        await state.broadcast()
        return JSONResponse(
            {
                "ok": True,
                "user_caps": state.safety.user_caps,
                "effective_caps": {c: state.safety.cap_for(c) for c in ("A", "B")},
            }
        )

    @app.post("/api/intensity")
    async def api_intensity(body: dict) -> JSONResponse:
        """整体强度档位（只乘 AI 输出强度，与对话无关；重启回默认「中」）：{level:"轻"|"中"|"重"}。"""
        level = str(body.get("level") or "").strip()
        if level not in ("轻", "中", "重"):
            return JSONResponse({"error": "level 只能是 轻/中/重"}, status_code=400)
        state.safety.set_intensity_level(level)
        await state.broadcast()
        return JSONResponse(
            {
                "ok": True,
                "intensity_level": state.safety.intensity_level,
                "strength_scale": state.safety.scale,
            }
        )

    @app.post("/api/character/profile")
    async def api_character_profile(body: dict) -> JSONResponse:
        """切换角色/风格：{role: "触手", profile: "调教"}，保存并热加载；目标 DLC 未安装时拒绝。"""
        role = str(body.get("role") or "").strip()
        profile = str(body.get("profile") or "").strip()
        # 以文件当前状态为准：先热加载再校验，避免陈旧内存配置放行未安装的 DLC
        reload_character(cfg)
        roles = {r["name"]: r for r in (cfg["character"].get("roles") or [])}
        if not role:
            role = str(cfg["character"].get("role") or "")
        if role not in roles:
            return JSONResponse({"error": f"未知角色，可用：{list(roles)}"}, status_code=400)
        rmeta = roles[role]
        avail = {p["name"]: p["available"] for p in rmeta["profiles"]}
        if not profile:
            profile = avail and next(iter(avail))
        if profile not in avail:
            return JSONResponse({"error": f"未知风格版本，可用：{list(avail)}"}, status_code=400)
        if not avail.get(profile, True):
            return JSONResponse(
                {
                    "error": f"「{rmeta['label']}·{profile}」暂不可用（内容未内置）。",
                },
                status_code=400,
            )
        save_character_runtime(cfg, role=role, profile=profile)
        await state.broadcast()
        return JSONResponse(
            {"ok": True, "role": cfg["character"]["role"], "profile": cfg["character"]["profile"]}
        )

    @app.post("/api/character/nick")
    async def api_character_nick(body: dict) -> JSONResponse:
        """改玩家昵称：{nick: "..."}，保存并热加载。"""
        nick = str(body.get("nick") or "").strip()
        if not nick or len(nick) > 20:
            return JSONResponse({"error": "昵称不能为空且不超过 20 字"}, status_code=400)
        save_character_runtime(cfg, player_nick=nick)
        await state.broadcast()
        return JSONResponse({"ok": True, "player_nick": cfg["character"]["player_nick"]})

    @app.post("/api/character/lang")
    async def api_character_lang(body: dict) -> JSONResponse:
        """中英内容切换：{lang: "zh"|"en"}，保存并热加载；英文稿缺失时保持中文。"""
        lang = str(body.get("lang") or "").strip()
        if lang not in ("zh", "en"):
            return JSONResponse({"error": "lang 只能是 zh/en"}, status_code=400)
        save_character_runtime(cfg, lang=lang)
        # 目标角色无英文稿：自动退回中文（前端 EN 档本就禁用，此为多端/切角色竞态兜底）
        if lang == "en" and not cfg["character"].get("en_available"):
            save_character_runtime(cfg, lang="zh")
        await state.broadcast()
        return JSONResponse(
            {
                "ok": True,
                "lang": str(cfg["character"].get("lang") or "zh"),
                "en_available": bool(cfg["character"].get("en_available")),
            }
        )

    # （DLC 导入机制已随闭源移除：内容全部内置 content/roles/ 与 content/pack/dungeon/）

    # ---------- 地牢（紫金地牢，M4） ----------
    @app.get("/api/dungeon/state")
    async def api_dungeon_state() -> JSONResponse:
        return JSONResponse(state.dungeon.to_state())

    @app.post("/api/dungeon/start")
    async def api_dungeon_start(body: dict) -> JSONResponse:
        try:
            result = await state.dungeon.start(
                active_themes=body.get("active_themes"),
                mix_policy=str(body.get("mix_policy") or "mixed_pool"),
                floors=int(body.get("floors") or 3),
                seed=body.get("seed"),
                map_mode=bool(body.get("map_mode", False)),
            )
        except Exception as exc:  # noqa: BLE001
            return JSONResponse({"error": str(exc)}, status_code=400)
        await state.broadcast()
        return JSONResponse(result)

    @app.post("/api/dungeon/advance")
    async def api_dungeon_advance(body: dict) -> JSONResponse:
        try:
            result = await state.dungeon.advance(
                choice_id=body.get("choice_id"),
                text=body.get("text"),
                map_target=body.get("map_target"),
            )
        except Exception as exc:  # noqa: BLE001
            return JSONResponse({"error": str(exc)}, status_code=400)
        await state.broadcast()
        return JSONResponse(result)

    @app.post("/api/dungeon/save")
    async def api_dungeon_save(body: dict) -> JSONResponse:
        try:
            path = state.dungeon.save(str(body.get("slot") or "autosave"))
        except Exception as exc:  # noqa: BLE001
            return JSONResponse({"error": str(exc)}, status_code=400)
        return JSONResponse({"ok": True, "path": path})

    @app.post("/api/dungeon/load")
    async def api_dungeon_load(body: dict) -> JSONResponse:
        try:
            result = await state.dungeon.load(str(body.get("slot") or "autosave"))
        except Exception as exc:  # noqa: BLE001
            return JSONResponse({"error": str(exc)}, status_code=400)
        await state.broadcast()
        return JSONResponse(result)

    @app.post("/api/dungeon/restart")
    async def api_dungeon_restart(body: dict) -> JSONResponse:
        state.dungeon.restart()
        await state.broadcast()
        return JSONResponse({"ok": True})

    @app.post("/api/autopilot")
    async def api_autopilot(body: dict) -> JSONResponse:
        """自动运行开关：{enabled: true/false}。AI 自主观察、调整设备并发言；摄像头/麦克风跟随启停。"""
        enabled = bool(body.get("enabled"))
        state.loop.set_autopilot(enabled)
        await state.set_sensors(enabled)
        await state.broadcast()
        return JSONResponse({"ok": True, "autopilot": bool(state.loop.autopilot)})

    @app.post("/api/autopilot/interval")
    async def api_autopilot_interval(body: dict) -> JSONResponse:
        """自动运行间隔：{interval_s: 5~30}。改内存值并持久化到 config.yaml 的 autopilot.interval_s。"""
        try:
            value = float(body.get("interval_s", 12))
        except (TypeError, ValueError):
            return JSONResponse({"error": "间隔必须是 5–30 秒"}, status_code=400)
        value = state.loop.set_autopilot_interval(value)
        try:
            save_autopilot_interval(cfg, value)
        except Exception:  # noqa: BLE001
            state.logger.exception("自动运行间隔保存失败，保留内存值")
        await state.broadcast()
        return JSONResponse({"ok": True, "interval_s": value})

    @app.post("/api/test_mode")
    async def api_test_mode(body: dict) -> JSONResponse:
        """测试模式开关：{enabled: true/false}。不连郊狼，用模拟设备试跑全流程（不会真电击）。"""
        result = await state.set_test_mode(bool(body.get("enabled", False)))
        await state.broadcast()
        return JSONResponse(result)

    # ---------- AI 模型配置（设置页填写，保存即生效） ----------
    @app.get("/api/settings/llm")
    async def api_settings_llm() -> JSONResponse:
        llm = cfg.get("llm", {})
        key = str(llm.get("api_key") or "")
        masked = (
            key[:4] + "*" * (len(key) - 8) + key[-4:]
            if len(key) > 12
            else ("*" * len(key) or "")
        )
        return JSONResponse(
            {
                "base_url": str(llm.get("base_url", "")),
                "model": str(llm.get("model", "")),
                "api_key_masked": masked,
                "has_key": bool(key),
                "saved": (PROJECT_ROOT / "config" / "config.yaml").exists(),
                "json_mode": bool(llm.get("json_mode", True)),
            }
        )

    def _patch_llm_text(
        text: str, api_key: str, base_url: str, model: str, json_mode: bool | None
    ) -> str:
        """文本级更新 config.yaml 的 llm 小节（仅 2 空格缩进键），保留其余注释与内容。"""
        lines = text.splitlines()
        out: list[str] = []
        in_llm = False
        for ln in lines:
            if ln and not ln.startswith(" "):
                in_llm = ln.startswith("llm:")
                out.append(ln)
                continue
            if in_llm and ln.startswith("  ") and not ln.startswith("    "):
                key = ln.lstrip().split(":", 1)[0]
                if key == "api_key":
                    esc = (
                        api_key.replace("\\", "\\\\")
                        .replace('"', '\\"')
                        .replace("\n", "\\n")
                        .replace("\r", "")
                    )
                    out.append(f'  api_key: "{esc}"')
                    continue
                if key == "base_url":
                    out.append(f'  base_url: "{base_url}"')
                    continue
                if key == "model":
                    out.append(f'  model: "{model}"')
                    continue
                if key == "json_mode" and json_mode is not None:
                    out.append(f"  json_mode: {str(bool(json_mode)).lower()}")
                    continue
            out.append(ln)
        return "\n".join(out) + "\n"

    @app.post("/api/settings/llm")
    async def api_settings_llm_save(body: dict) -> JSONResponse:
        """保存 AI 配置并热加载：{api_key, base_url, model, json_mode?}；config.yaml 不存在时自动从示例生成。"""
        api_key = str(body.get("api_key") or "").strip()
        base_url = str(body.get("base_url") or "").strip()
        model = str(body.get("model") or "").strip()
        json_mode = body.get("json_mode") if isinstance(body.get("json_mode"), bool) else None
        if not base_url or not model:
            return JSONResponse({"error": "地址与模型名不能为空"}, status_code=400)
        cfg_path = PROJECT_ROOT / "config" / "config.yaml"
        example = PROJECT_ROOT / "config" / "config.example.yaml"
        if not cfg_path.exists():
            cfg_path.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
        cfg_path.write_text(
            _patch_llm_text(
                cfg_path.read_text(encoding="utf-8"), api_key, base_url, model, json_mode
            ),
            encoding="utf-8",
        )
        # 同步内存并热加载（key 留空时回退环境变量 DGLAB_LLM_API_KEY）
        llm = cfg.setdefault("llm", {})
        llm["api_key"] = api_key or os.environ.get("DGLAB_LLM_API_KEY", "")
        llm["base_url"] = base_url
        llm["model"] = model
        if json_mode is not None:
            llm["json_mode"] = json_mode
        old = state.llm
        state.llm = LLM(cfg)
        state.loop.llm = state.llm
        with contextlib.suppress(Exception):
            await old.client.aclose()
        await state.broadcast()
        return JSONResponse({"ok": True, "model": model})

    @app.post("/api/settings/llm/test")
    async def api_settings_llm_test(body: dict) -> JSONResponse:
        """测试连接：用表单值发一条最小请求（不保存）。"""
        api_key = str(body.get("api_key") or "").strip()
        base = str(body.get("base_url") or "").strip()
        model = str(body.get("model") or "").strip()
        # 安全：环境变量密钥只允许用于「已保存的 Base URL」（与请求体地址一致时），
        # 防止调用者指定任意地址让后端把环境密钥外发（SSRF + 凭据外传）
        if not api_key and base.rstrip("/") == str(cfg["llm"].get("base_url", "")).rstrip("/"):
            api_key = os.environ.get("DGLAB_LLM_API_KEY", "")
        if not api_key or not base or not model:
            return JSONResponse({"ok": False, "error": "请先填写 API Key、地址与模型名"})
        try:
            async with httpx.AsyncClient(
                timeout=20, trust_env=bool(cfg["llm"].get("trust_env", False))
            ) as client:
                r = await client.post(
                    f"{base.rstrip('/')}/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": "hi"}],
                        "max_tokens": 1,
                    },
                )
            if r.status_code == 200:
                return JSONResponse({"ok": True, "detail": "连接成功，模型可用"})
            if r.status_code == 401:
                return JSONResponse(
                    {
                        "ok": False,
                        "error": "API Key 无效或未填（官方与中转站的密钥不通用，请确认 Base URL 与密钥配套）",
                    }
                )
            if r.status_code == 400:
                return JSONResponse(
                    {"ok": False, "error": "请求参数不被支持（中转站常见）：请核对模型名，或关闭 JSON 模式"}
                )
            return JSONResponse({"ok": False, "error": f"HTTP {r.status_code}: {r.text[:200]}"})
        except Exception as exc:  # noqa: BLE001
            return JSONResponse({"ok": False, "error": str(exc)[:300]})

    def _patch_app_text(text: str, check_update: bool) -> str:
        """文本级更新 config.yaml 的 app 小节（仅 2 空格缩进键），缺失时插入。"""
        lines = text.splitlines()
        out: list[str] = []
        in_app = False
        patched = False
        for ln in lines:
            if ln and not ln.startswith(" "):
                in_app = ln.startswith("app:")
                out.append(ln)
                continue
            if in_app and ln.startswith("  ") and not ln.startswith("    "):
                key = ln.lstrip().split(":", 1)[0]
                if key == "check_update":
                    out.append(f"  check_update: {str(bool(check_update)).lower()}")
                    patched = True
                    continue
            out.append(ln)
        if not patched:
            idx = next((i for i, l in enumerate(out) if l.strip() == "app:"), -1)
            if idx >= 0:
                out.insert(idx + 1, f"  check_update: {str(bool(check_update)).lower()}")
        return "\n".join(out) + "\n"

    # ---------- 更新检测 ----------
    @app.get("/api/update")
    async def api_update() -> JSONResponse:
        await state.update.check()
        await state.broadcast()
        return JSONResponse(state.update.to_state(_app_version()))

    @app.post("/api/update")
    async def api_update_set(body: dict) -> JSONResponse:
        """开关自动检查更新（持久化到 config.yaml app.check_update）。"""
        if isinstance(body.get("enabled"), bool):
            state.update.enabled = body["enabled"]
            cfg["app"]["check_update"] = state.update.enabled
            cfg_path = PROJECT_ROOT / "config" / "config.yaml"
            example = PROJECT_ROOT / "config" / "config.example.yaml"
            if not cfg_path.exists():
                cfg_path.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
            cfg_path.write_text(
                _patch_app_text(cfg_path.read_text(encoding="utf-8"), state.update.enabled),
                encoding="utf-8",
            )
            if state.update.enabled:
                await state.update.check()
            await state.broadcast()
        return JSONResponse({"ok": True, **state.update.to_state(_app_version())})

    # ---------- 实时推送 ----------
    @app.websocket("/ws")
    async def ws_endpoint(ws: WebSocket) -> None:
        await ws.accept()
        state.ws_clients.add(ws)
        state._on_ws_clients_change()
        await ws.send_json({"type": "state", "data": state.build_state()})
        try:
            while True:
                await ws.receive_text()  # 客户端心跳/忽略
        except WebSocketDisconnect:
            pass
        finally:
            state.ws_clients.discard(ws)
            state._on_ws_clients_change()

    # 兜底：任意非 API/静态资源路径都回首页（用户输错地址/旧收藏夹不再 404）。
    # 必须在所有 /api 路由与 /assets 挂载之后注册，API 优先命中。
    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str) -> Response:
        if full_path.startswith(("api/", "assets/")):
            raise HTTPException(status_code=404, detail="Not Found")
        if (FRONTEND_DIST / "index.html").exists():
            return FileResponse(FRONTEND_DIST / "index.html")
        return Response(
            "前端尚未构建：请在 frontend\\ 目录执行 npm install && npm run build",
            media_type="text/plain; charset=utf-8",
        )

    return app


app = make_app()


if __name__ == "__main__":
    import uvicorn

    cfg = load_config()
    uvicorn.run(
        app,
        host=cfg["app"]["host"],
        port=int(cfg["app"]["port"]),
        log_level="info",
    )
