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
import zipfile
from pathlib import Path

import httpx
import qrcode
from fastapi import FastAPI, File, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from .audio import AudioManager
from .camera import Camera
from .config import (
    load_config,
    patch_character_add_role,
    patch_character_prompt_file,
    reload_character,
    save_character_runtime,
    save_device_channels,
)
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


def _app_version() -> str:
    """版本号：打包时写入 version.txt；源码运行时显示 dev。"""
    f = PROJECT_ROOT / "version.txt"
    if f.exists():
        v = f.read_text(encoding="utf-8").strip()
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
        self.layout: dict = {}  # 前端上报的三栏布局（监测/调试用）
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
        state["sensors"] = dict(self.sensor_switches)
        state["relay"] = self.relay.to_state()
        state["audio"] = self.audio.to_state()
        state["layout"] = dict(self.layout)
        state["character"] = self.cfg["character"]["name"]
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
                    "error": f"「{rmeta['label']}·{profile}」的 DLC 未安装：请先在「角色设置」导入对应 DLC 包。",
                    "detail": "dlc_missing",
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

    @app.post("/api/dlc/import")
    async def api_dlc_import(file: UploadFile = File(...)) -> JSONResponse:
        """导入 DLC：上传 .zip（解出全部 .md）或单个 .md → 拷进 content\\pack\\ 并自动接通 character.yaml。

        不用重启：改完即热加载，前端可立即切换该风格。
        """
        name = file.filename or ""
        low = name.lower()
        if not (low.endswith(".zip") or low.endswith(".md")):
            return JSONResponse({"error": "只支持 .zip 或 .md 文件"}, status_code=400)
        data = await file.read()
        if not data:
            return JSONResponse({"error": "文件为空"}, status_code=400)
        if len(data) > 50 * 1024 * 1024:
            return JSONResponse({"error": "文件过大（上限 50MB）"}, status_code=400)

        pack_dir = PROJECT_ROOT / "content" / "pack"
        pack_dir.mkdir(parents=True, exist_ok=True)

        mds: dict[str, bytes] = {}
        dlc_folder = ""
        if low.endswith(".zip"):
            try:
                zf = zipfile.ZipFile(io.BytesIO(data))
            except zipfile.BadZipFile:
                return JSONResponse({"error": "zip 包损坏或格式不对"}, status_code=400)
            with zf:
                for n in zf.namelist():
                    # Windows 压缩工具不写 UTF-8 标志，先按 cp437 还原原始字节再按 UTF-8 解码中文名
                    fixed = n
                    try:
                        fixed = n.encode("cp437").decode("utf-8")
                    except (UnicodeEncodeError, UnicodeDecodeError):
                        pass
                    bn = Path(fixed).name
                    if not bn.lower().endswith(".md") or bn.startswith("."):
                        continue
                    if not dlc_folder:
                        parts = [p for p in Path(fixed).parts if p not in ("", ".", "..")]
                        if len(parts) > 1:
                            dlc_folder = parts[0]
                    mds[bn] = zf.read(n)
            if not mds:
                return JSONResponse({"error": "zip 里没有 .md 文件"}, status_code=400)
        else:
            mds[name] = data

        if not dlc_folder:
            dlc_folder = Path(name).stem or "DLC导入"
        dlc_dir = pack_dir / dlc_folder
        dlc_dir.mkdir(parents=True, exist_ok=True)
        for bn, content in mds.items():
            (dlc_dir / bn).write_bytes(content)

        # 自动接通：按 DLC 目录名解析「角色-风格」（DLC<序号>-<角色>-<风格>），
        # 角色已存在则接通其风格档；新角色自动注册角色块；旧式单 md 按当前角色匹配
        prompt_md = next((b for b in mds if "角色提示词" in b), None) or next(
            (b for b in mds if "提示词" in b), None
        )
        patched_profile = None
        patched_role = None
        if prompt_md:
            reload_character(cfg)
            char_path = Path(cfg["character_file"])
            if not char_path.is_absolute():
                char_path = PROJECT_ROOT / char_path
            rel = f"content/pack/{dlc_folder}/{prompt_md}"

            m = re.match(r"^DLC\d+-(.+?)-(.+)$", dlc_folder)
            dlc_role = (m.group(1) if m else "").strip()
            dlc_style = (m.group(2) if m else "").strip()
            roles_map = {r["name"]: r for r in (cfg["character"].get("roles") or [])}

            if dlc_role and dlc_role in roles_map:
                # 已知角色：接通其下匹配的风格档
                profiles_of = [p["name"] for p in roles_map[dlc_role]["profiles"]]
                target = next((p for p in profiles_of if p and p in prompt_md), None)
                if target is None:
                    target = profiles_of[0] if profiles_of else None
                if target and patch_character_prompt_file(char_path, target, rel, role=dlc_role):
                    patched_profile = target
                    patched_role = dlc_role
            elif dlc_role:
                # 新角色：自动注册角色块（傻瓜式，无需手改配置）
                level = "重" if dlc_style and "调教" in dlc_style and dlc_role != "触手" else "中"
                narrative = "触手" if dlc_role == "触手" else "装置"
                style = dlc_style or "调教"
                if patch_character_add_role(char_path, dlc_role, dlc_role, style, level, rel, narrative):
                    patched_profile = style
                    patched_role = dlc_role
            else:
                # 旧式（单 md / 无 DLC 目录名）：当前角色内匹配
                avail = cfg["character"].get("profile_available") or {}
                profiles = list(cfg["character"].get("profiles") or [])
                cur_role = str(cfg["character"].get("role") or "")
                target = next((p for p in profiles if p and p in prompt_md), None)
                if target is None:
                    target = next((p for p in profiles if p != "纯爱" and not avail.get(p, True)), None)
                if target is None and "调教" in profiles:
                    target = "调教"
                if target and patch_character_prompt_file(char_path, target, rel, role=cur_role):
                    patched_profile = target
                    patched_role = cur_role
            reload_character(cfg)

        await state.broadcast()
        return JSONResponse(
            {
                "ok": True,
                "dir": dlc_folder,
                "files": sorted(mds),
                "role": patched_role,
                "profile": patched_profile,
            }
        )

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
