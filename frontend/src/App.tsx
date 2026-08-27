import { useEffect, useState } from "react";
import TopBar, { type ViewName } from "./components/TopBar";
import Sidebar from "./components/Sidebar";
import DeviceStatus from "./components/DeviceStatus";
import ChannelControl from "./components/ChannelControl";
import PresetPanel from "./components/PresetPanel";
import BottomBar from "./components/BottomBar";
import ChatPanel from "./components/ChatPanel";
import { PairView, SettingsView } from "./components/views";
import { api } from "./api";
import { useApp, useChat, useLayout } from "./store";
import { doEstop } from "./commands";

export default function App() {
  const [view, setView] = useState<ViewName>("control");
  const sidebarW = useLayout((s) => s.sidebarW);
  const chatW = useLayout((s) => s.chatW);
  // 全局缩放：按窗口宽度缩放整页布局（0.8 ~ 1.3 倍）
  const [zoom, setZoom] = useState(1);
  useEffect(() => {
    const calc = () => {
      setZoom(Math.min(1.3, Math.max(0.8, window.innerWidth / 1600)));
    };
    calc();
    window.addEventListener("resize", calc);
    return () => window.removeEventListener("resize", calc);
  }, []);

  useEffect(() => {
    // 初始状态
    api
      .state()
      .then((s) => {
        useApp.getState().setState(s);
        if (s.config_info?.title) document.title = s.config_info.title;
      })
      .catch(() => {});
    // WebSocket 实时同步
    let ws: WebSocket;
    let closed = false;
    const connect = () => {
      if (closed) return;
      const proto = location.protocol === "https:" ? "wss:" : "ws:";
      ws = new WebSocket(proto + "//" + location.host + "/ws");
      ws.onmessage = (ev) => {
        const msg = JSON.parse(ev.data);
        if (msg.type === "state") {
          useApp.getState().setState(msg.data);
        } else if (msg.type === "chat") {
          const extra: string[] = [];
          for (const e of msg.executed ?? []) extra.push("▶ " + e.label);
          for (const x of msg.dropped ?? []) extra.push("✖ " + x.reason);
          useChat.getState().push({ role: "ai", text: msg.line ?? "", actions: extra.join("\n") });
        }
      };
      ws.onclose = () => setTimeout(connect, 2000);
    };
    connect();
    // 空格急停（不在输入框时）
    const onKey = (e: KeyboardEvent) => {
      const tag = (document.activeElement?.tagName ?? "").toUpperCase();
      if (e.code === "Space" && !["INPUT", "TEXTAREA"].includes(tag)) {
        e.preventDefault();
        void doEstop();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => {
      closed = true;
      ws?.close();
      document.removeEventListener("keydown", onKey);
    };
  }, []);

  return (
    <div className="flex h-full flex-col" style={{ zoom }}>
      <TopBar view={view} onView={setView} />
      <div
        className="grid min-h-0 flex-1"
        style={{ gridTemplateColumns: `${sidebarW}px 4px 1fr 4px ${chatW}px` }}
      >
        <Sidebar view={view} onView={setView} />
        <Resizer side="left" />
        <main className="min-h-0 overflow-y-auto px-4 pb-14 pt-3">
          {view === "control" && (
            <div className="flex h-full min-h-0 flex-col gap-2.5">
              <div className="min-h-0 flex-1">
                <DeviceStatus />
              </div>
              <ChannelControl />
              <PresetPanel />
            </div>
          )}
          {view === "pair" && <PairView />}
          {view === "settings" && <SettingsView />}
        </main>
        <Resizer side="right" />
        <ChatPanel />
      </div>
      <BottomBar />
    </div>
  );
}

/** 拖拽调节三栏宽度（左=侧边栏，右=聊天面板），宽度持久化 */
function Resizer({ side }: { side: "left" | "right" }) {
  const setSidebarW = useLayout((s) => s.setSidebarW);
  const setChatW = useLayout((s) => s.setChatW);

  const onDown = (e: React.PointerEvent) => {
    e.preventDefault();
    const startX = e.clientX;
    const startW = side === "left" ? useLayout.getState().sidebarW : useLayout.getState().chatW;
    const move = (ev: PointerEvent) => {
      const dx = ev.clientX - startX;
      if (side === "left") setSidebarW(Math.min(360, Math.max(160, startW + dx)));
      else setChatW(Math.min(720, Math.max(300, startW - dx)));
    };
    const up = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  };

  return (
    <div
      onPointerDown={onDown}
      title="拖拽调节宽度"
      className="w-full cursor-col-resize bg-transparent transition-colors hover:bg-accent/40 active:bg-accent/60"
    />
  );
}
