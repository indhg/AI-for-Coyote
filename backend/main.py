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
import socket
import sys
import urllib.parse
from pathlib import Path

import httpx
import qrcode
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from .audio import AudioManager
from .camera import Camera
from .config import load_config, reload_character, save_character_runtime, save_device_channels
from .game_loop import GameLoop
from .llm import LLM
from .logging_utils import setup_logging
from .relay_client import RelayClient
from .safety import SafetyManager

# 打包（PyInstaller）后以 exe 所在目录为项目根；开发时以仓库根
if getattr(sys, "frozen", False):
    PROJECT_ROOT = Path(sys.executable).resolve().parent
else:
    PROJECT_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"


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
        self.relay = RelayClient(
            cfg["relay"]["url"],
            reconnect_delay_s=float(cfg["relay"]["reconnect_delay_s"]),
            on_event=self.on_relay_event,
            on_action=self.on_relay_action,
        )
        self.llm = LLM(cfg)
        self.camera = Camera(cfg)
        self.audio = AudioManager(
            cfg, on_text=self.on_audio_text, on_moan=self.on_audio_moan
        )
        self.loop = GameLoop(cfg, self.llm, self.safety, self.relay, self.camera, self.audio)
        self.loop.on_ai_turn = self.broadcast_chat  # AI 主动回合推送到页面聊天区

        self.ws_clients: set[WebSocket] = set()
        self.tasks: list[asyncio.Task] = []
        self.auto_opened = False
        self.sensors_on = False
        self.sensor_watch_task: asyncio.Task | None = None

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
            client = self.relay.clients.get(self.relay.first_client_id() or "")
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
        state["relay"] = self.relay.to_state()
        state["audio"] = self.audio.to_state()
        state["character"] = self.cfg["character"]["name"]
        state["config_info"] = {
            "model": self.cfg["llm"]["model"],
            "character_file": str(self.cfg["character_file"]),
            "waveforms_file": str(PROJECT_ROOT / "config" / "waveforms.yaml"),
            "title": str(self.cfg["app"].get("title", "郊狼 · AI 驯服师")),
            "profile": str(self.cfg["character"].get("profile") or "调教"),
            "player_nick": str(self.cfg["character"].get("player_nick") or "小柳"),
        }
        return state

    # ---------- 传感器开关（跟随自动运行；浏览器断开超时自动关） ----------
    async def set_sensors(self, on: bool) -> None:
        """自动运行开启时启动摄像头/麦克风，关闭时停止（config.enabled 为前置许可）。"""
        self.sensors_on = bool(on)
        if on:
            await self.camera.start()
            await self.audio.start()
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

    # ---------- 生命周期 ----------
    async def start_background(self) -> None:
        self.tasks.append(asyncio.create_task(self.relay.run()))
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

    # React 构建产物的静态资源（存在时才挂载）
    if (FRONTEND_DIST / "assets").exists():
        app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/api/state")
    async def api_state() -> JSONResponse:
        return JSONResponse(state.build_state())

    @app.get("/api/qrcode.png")
    async def api_qrcode() -> Response:
        controller_id = state.relay.controller_id
        if not controller_id:
            return Response("中继未连接，暂无配对码", status_code=503, media_type="text/plain")
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
        controller_id = state.relay.controller_id
        if not controller_id:
            return JSONResponse({"error": "中继未连接"}, status_code=503)
        lan_ip = cfg["relay"]["lan_ip"]
        if lan_ip == "auto":
            lan_ip = get_lan_ip()
        return JSONResponse({"url": build_pair_url(cfg, lan_ip, controller_id)})

    @app.get("/api/network")
    async def api_network() -> JSONResponse:
        """网络自检：本机 IP 列表 + 当前配对地址。"""
        controller_id = state.relay.controller_id
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

    @app.post("/api/device/channels/scale")
    async def api_device_channel_scale(body: dict) -> JSONResponse:
        """强度修正倍率（只作用于 AI 的强度）：{channel:"A", scale:0.7|1.0|1.3}。"""
        ch = str(body.get("channel") or "").strip().upper()
        if ch not in ("A", "B"):
            return JSONResponse({"error": "channel 只能是 A 或 B"}, status_code=400)
        try:
            scale = float(body.get("scale", 1.0))
        except (TypeError, ValueError):
            return JSONResponse({"error": "scale 必须是数字"}, status_code=400)
        state.safety.set_strength_scale(ch, scale)
        await state.broadcast()
        return JSONResponse({"ok": True, "strength_scale": state.safety.scale})

    @app.post("/api/character/profile")
    async def api_character_profile(body: dict) -> JSONResponse:
        """切换风格版本：{profile: "纯爱"|"调教"}，保存并热加载；目标版本 DLC 未安装时拒绝。"""
        profile = str(body.get("profile") or "").strip()
        # 以文件当前状态为准：先热加载再校验，避免陈旧内存配置放行未安装的 DLC
        reload_character(cfg)
        available = list(cfg["character"].get("profiles") or [])
        if profile not in available:
            return JSONResponse({"error": f"未知版本，可用：{available}"}, status_code=400)
        if not cfg["character"].get("profile_available", {}).get(profile, True):
            return JSONResponse(
                {
                    "error": (
                        f"「{profile}」版的 DLC 未安装：请把对应 DLC 目录放入 content\\pack\\，"
                        "并在 config\\character.yaml 中启用该版本的 prompt_file 后重启程序。"
                    ),
                    "detail": "dlc_missing",
                },
                status_code=400,
            )
        save_character_runtime(cfg, profile=profile)
        await state.broadcast()
        return JSONResponse({"ok": True, "profile": cfg["character"]["profile"]})

    @app.post("/api/character/nick")
    async def api_character_nick(body: dict) -> JSONResponse:
        """改玩家昵称：{nick: "..."}，保存并热加载。"""
        nick = str(body.get("nick") or "").strip()
        if not nick or len(nick) > 20:
            return JSONResponse({"error": "昵称不能为空且不超过 20 字"}, status_code=400)
        save_character_runtime(cfg, player_nick=nick)
        await state.broadcast()
        return JSONResponse({"ok": True, "player_nick": cfg["character"]["player_nick"]})

    @app.post("/api/autopilot")
    async def api_autopilot(body: dict) -> JSONResponse:
        """自动运行开关：{enabled: true/false}。AI 自主观察、调整设备并发言；摄像头/麦克风跟随启停。"""
        enabled = bool(body.get("enabled"))
        state.loop.set_autopilot(enabled)
        await state.set_sensors(enabled)
        await state.broadcast()
        return JSONResponse({"ok": True, "autopilot": bool(state.loop.autopilot)})

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
            }
        )

    def _patch_llm_text(text: str, api_key: str, base_url: str, model: str) -> str:
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
                    out.append(f'  api_key: "{api_key}"')
                    continue
                if key == "base_url":
                    out.append(f"  base_url: {base_url}")
                    continue
                if key == "model":
                    out.append(f"  model: {model}")
                    continue
            out.append(ln)
        return "\n".join(out) + "\n"

    @app.post("/api/settings/llm")
    async def api_settings_llm_save(body: dict) -> JSONResponse:
        """保存 AI 配置并热加载：{api_key, base_url, model}；config.yaml 不存在时自动从示例生成。"""
        api_key = str(body.get("api_key") or "").strip()
        base_url = str(body.get("base_url") or "").strip()
        model = str(body.get("model") or "").strip()
        if not base_url or not model:
            return JSONResponse({"error": "地址与模型名不能为空"}, status_code=400)
        cfg_path = PROJECT_ROOT / "config" / "config.yaml"
        example = PROJECT_ROOT / "config" / "config.example.yaml"
        if not cfg_path.exists():
            cfg_path.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
        cfg_path.write_text(
            _patch_llm_text(cfg_path.read_text(encoding="utf-8"), api_key, base_url, model),
            encoding="utf-8",
        )
        # 同步内存并热加载（key 留空时回退环境变量 DGLAB_LLM_API_KEY）
        llm = cfg.setdefault("llm", {})
        llm["api_key"] = api_key or os.environ.get("DGLAB_LLM_API_KEY", "")
        llm["base_url"] = base_url
        llm["model"] = model
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
        api_key = str(body.get("api_key") or "").strip() or os.environ.get("DGLAB_LLM_API_KEY", "")
        base = str(body.get("base_url") or "").strip()
        model = str(body.get("model") or "").strip()
        if not api_key or not base or not model:
            return JSONResponse({"ok": False, "error": "请先填写 API Key、地址与模型名"})
        try:
            async with httpx.AsyncClient(timeout=20) as client:
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
            return JSONResponse({"ok": False, "error": f"HTTP {r.status_code}: {r.text[:200]}"})
        except Exception as exc:  # noqa: BLE001
            return JSONResponse({"ok": False, "error": str(exc)[:300]})

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
