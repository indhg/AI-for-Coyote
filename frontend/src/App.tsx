import { useEffect, useRef, useState } from "react";
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

/** 空格长按触发急停的时长（毫秒，与进度条动画同步） */
const ESTOP_HOLD_MS = 1000;

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

  // 空格长按急停的进行中状态与计时器
  const [holding, setHolding] = useState(false);
  const holdTimer = useRef<number | null>(null);
  const cancelHold = () => {
    if (holdTimer.current !== null) {
      window.clearTimeout(holdTimer.current);
      holdTimer.current = null;
    }
    setHolding(false);
  };

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
    // 空格长按 1s 急停（防误触：松手 / 窗口失焦即取消；已急停时不重复触发）
    const onKeyDown = (e: KeyboardEvent) => {
      const tag = (document.activeElement?.tagName ?? "").toUpperCase();
      if (e.code !== "Space" || ["INPUT", "TEXTAREA"].includes(tag)) return;
      e.preventDefault();
      if (e.repeat) return;
      if (useApp.getState().state?.estop) return;
      setHolding(true);
      holdTimer.current = window.setTimeout(() => {
        holdTimer.current = null;
        setHolding(false);
        void doEstop();
      }, ESTOP_HOLD_MS);
    };
    const onKeyUp = (e: KeyboardEvent) => {
      if (e.code === "Space") cancelHold();
    };
    const onBlur = () => cancelHold();
    document.addEventListener("keydown", onKeyDown);
    document.addEventListener("keyup", onKeyUp);
    window.addEventListener("blur", onBlur);
    return () => {
      closed = true;
      ws?.close();
      document.removeEventListener("keydown", onKeyDown);
      document.removeEventListener("keyup", onKeyUp);
      window.removeEventListener("blur", onBlur);
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
      {holding && (
        <div className="pointer-events-none fixed inset-x-0 bottom-20 z-50 flex justify-center">
          <div className="w-64 rounded-[10px] border border-line bg-panel2 px-4 py-3 shadow-lg">
            <div className="flex items-baseline justify-between">
              <span className="text-sm font-semibold text-text">「急停中…」</span>
              <span className="text-xs text-muted">松开取消</span>
            </div>
            <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-ink3">
              <div
                className="h-full rounded-full bg-bad"
                style={{
                  transformOrigin: "left",
                  animation: `estop-fill ${ESTOP_HOLD_MS}ms linear forwards`,
                }}
              />
            </div>
          </div>
        </div>
      )}
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
