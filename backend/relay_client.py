# -*- coding: utf-8 -*-
"""中继客户端：连接 dglab-websocket-server v4，维护配对与设备状态，自动重连。

协议要点（已核对源码）：
- 控制方连 ws://host:9998，收 {"type":"hello","clientId":...}；
- 被控方（DG-LAB 4 APP）用 ?tid=控制方clientId 接入，控制方收 client_attached；
- 控制方下发 {"type":"message","clientId":被控方ID,"data":{RPC}}；
- APP 上行：devices.snapshot（设备列表）、slots.patch（强度/状态）、custom.action（反馈按钮）。
"""
import asyncio
import json
import logging

import websockets

logger = logging.getLogger("ai-for-coyote.relay")


def _deep_merge(base: dict, patch: dict) -> dict:
    for key, value in (patch or {}).items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
    return base


class RelayClient:
    def __init__(
        self,
        url: str,
        reconnect_delay_s: float = 3,
        on_event=None,   # async fn(event: str, payload: dict)
        on_action=None,  # async fn(action: int, client_id: str)
    ) -> None:
        self.url = url
        self.reconnect_delay_s = reconnect_delay_s
        self.on_event = on_event
        self.on_action = on_action

        self.ws = None
        self.status = "disconnected"      # disconnected/connecting/waiting/paired
        self.controller_id: str | None = None
        self.clients: dict[str, dict] = {}  # clientId -> {devices, props, slotState}
        self.last_error: str = ""

    # ---------- 状态 ----------
    def get_slot_id(self, client_id: str | None = None) -> str | None:
        """取设备 slotId（默认优先选有真实设备的被控方）。"""
        if client_id is None:
            cid = self.first_client_id()
        else:
            cid = client_id
        client = self.clients.get(cid or "")
        if not client:
            return None
        devices = client.get("devices") or []
        return devices[0]["slotId"] if devices else None

    def first_client_id(self) -> str | None:
        """取第一个被控方 ID；优先选择暴露了设备（有 slotId）的。"""
        for cid, client in self.clients.items():
            if client.get("devices"):
                return cid
        return next(iter(self.clients), None)

    def to_state(self) -> dict:
        paired = []
        for cid, client in self.clients.items():
            paired.append(
                {
                    "clientId": cid,
                    "slotId": self.get_slot_id(cid),
                    "devices": [
                        {"slotId": d.get("slotId"), "name": d.get("name"),
                         "type": d.get("type")}
                        for d in (client.get("devices") or [])
                    ],
                    "props": client.get("props", {}),
                    "slotState": client.get("slotState", {}),
                }
            )
        return {
            "status": self.status,
            "controller_id": self.controller_id,
            "url": self.url,
            "clients": paired,
            "last_error": self.last_error,
        }

    # ---------- 连接与收发 ----------
    async def run(self) -> None:
        """常驻任务：连接 + 自动重连。"""
        while True:
            try:
                self.status = "connecting"
                async with websockets.connect(
                    self.url, ping_interval=20, ping_timeout=20, open_timeout=10
                ) as ws:
                    self.ws = ws
                    logger.info("已连接中继服务器 %s", self.url)
                    await self._recv_loop(ws)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                self.last_error = str(exc)
                logger.warning("中继连接失败/断开: %s，%ss 后重连", exc, self.reconnect_delay_s)
            finally:
                self.ws = None
                self.status = "disconnected"
                self.clients.clear()
                await self._emit("disconnected", {"error": self.last_error})
            await asyncio.sleep(self.reconnect_delay_s)

    async def _recv_loop(self, ws) -> None:
        async for raw in ws:
            try:
                frame = json.loads(raw)
            except json.JSONDecodeError:
                continue
            self._handle_frame(frame)

    def _handle_frame(self, frame: dict) -> None:
        ftype = frame.get("type")
        if ftype == "hello":
            self.controller_id = frame.get("clientId")
            self.status = "waiting"
            logger.info("拿到控制方 ID: %s", self.controller_id)
            asyncio.create_task(self._emit("hello", frame))
        elif ftype == "client_attached":
            cid = frame.get("clientId")
            self.clients.setdefault(cid, {"devices": [], "props": {}, "slotState": {}})
            self.status = "paired"
            logger.info("APP 被控方接入: %s", cid)
            asyncio.create_task(self._emit("client_attached", frame))
        elif ftype == "client_disconnected":
            cid = frame.get("clientId")
            self.clients.pop(cid, None)
            if not self.clients:
                self.status = "waiting"
            logger.info("APP 被控方断开: %s", cid)
            asyncio.create_task(self._emit("client_disconnected", frame))
        elif ftype == "error":
            self.last_error = frame.get("code", "") + " " + str(frame.get("message", ""))
            logger.warning("服务器错误帧: %s", self.last_error)
            asyncio.create_task(self._emit("error", frame))
        elif ftype == "message":
            self._handle_message(frame)
        # heartbeat / pong / idle_timeout 忽略或已由上层处理

    def _handle_message(self, frame: dict) -> None:
        cid = frame.get("clientId") or self.first_client_id()
        data = frame.get("data")
        if not isinstance(data, dict) or cid is None:
            return
        # 只处理已知被控方的消息，避免产生幽灵客户端
        client = self.clients.get(cid)
        if client is None:
            return

        if data.get("t") == "ev":
            ev = data.get("ev")
            if ev == "devices.snapshot":
                client["devices"] = list(data.get("devices") or [])
                logger.info("设备快照: %s", [d.get("name") for d in client["devices"]])
                asyncio.create_task(self._emit("devices_snapshot", data))
            elif ev == "devices.patch":
                added = data.get("added") or []
                removed = set(data.get("removed") or [])
                client["devices"] = [
                    d for d in client["devices"] if d.get("slotId") not in removed
                ] + list(added)
                asyncio.create_task(self._emit("devices_patch", data))
            elif ev == "slots.patch":
                for slot in data.get("slots") or []:
                    sid = slot.get("slotId")
                    if not sid:
                        continue
                    props = _deep_merge(client["props"], slot.get("props") or {})
                    slot_state = _deep_merge(client["slotState"], slot.get("slotState") or {})
                    client["props"], client["slotState"] = props, slot_state
                    # 设备当前是这台 slot 时，直接给 props 打上 slotId 方便安全层读取
                    props.setdefault("slotId", sid)
                asyncio.create_task(self._emit("slots_patch", data))
            elif ev == "custom.action":
                action = data.get("action")
                logger.info("收到 APP 反馈按钮: %s (来自 %s)", action, cid)
                asyncio.create_task(self._emit("custom_action", data))
                if self.on_action:
                    asyncio.create_task(self.on_action(action, cid))
        elif data.get("t") == "resp":
            result = data.get("result")
            err = data.get("error")
            if err:
                logger.warning("RPC %s 失败: %s", data.get("reqId"), err)
            else:
                logger.debug("RPC %s 完成: %s", data.get("reqId"), result)

    async def send_frame(self, frame: dict) -> bool:
        """发送服务器帧；未连接返回 False。"""
        if self.ws is None:
            return False
        try:
            await self.ws.send(json.dumps(frame, ensure_ascii=False))
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("发送失败: %s", exc)
            return False

    async def _emit(self, event: str, payload: dict) -> None:
        if self.on_event:
            try:
                await self.on_event(event, payload)
            except Exception:  # noqa: BLE001
                logger.exception("事件回调异常: %s", event)
