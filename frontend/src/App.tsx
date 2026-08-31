import { useEffect, useRef, useState } from "react";
import TopBar, { type ViewName } from "./components/TopBar";
import Sidebar from "./components/Sidebar";
import DeviceStatus from "./components/DeviceStatus";
import ChannelControl from "./components/ChannelControl";
import PresetPanel from "./components/PresetPanel";
import BottomBar from "./components/BottomBar";
import ChatPanel from "./components/ChatPanel";
import NoticeToast from "./components/NoticeToast";
import { PairView, SettingsView } from "./components/views";
import { api } from "./api";
import { useApp, useChat, useLayout } from "./store";
import { doEstop } from "./commands";

/** 空格长按触发急停的时长（毫秒，与进度条动画同步） */
const ESTOP_HOLD_MS = 1000;

export default function App() {
  const [view, setView] = useState<ViewName>("control");
  const sidebarW = useLayout((s) => s.sidebarW);
  const controlW = useLayout((s) => s.controlW);
  const updateLayout = useLayout((s) => s.updateLayout);
  // 全局缩放：按窗口宽度缩放整页布局（0.8 ~ 1.3 倍）
  const [zoom, setZoom] = useState(1);
  useEffect(() => {
    const calc = () => {
      setZoom(Math.min(1.3, Math.max(0.8, window.innerWidth / 1600)));
      updateLayout(); // 三栏按固定比例随窗口宽度重算
    };
    calc();
    window.addEventListener("resize", calc);
    return () => window.removeEventListener("resize", calc);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 上报三栏布局给后端（调试/监测用，300ms 节流）
  useEffect(() => {
    const t = window.setTimeout(() => {
      api
        .reportLayout({
          sidebar_w: sidebarW,
          control_w: controlW,
          inner_width: window.innerWidth,
          zoom,
        })
        .catch(() => {});
    }, 300);
    return () => window.clearTimeout(t);
  }, [sidebarW, controlW, zoom]);

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
        style={{ gridTemplateColumns: `${sidebarW}px 1fr ${controlW}px` }}
      >
        <Sidebar view={view} onView={setView} />
        <ChatPanel />
        <main className="min-h-0 overflow-y-auto border-l border-line px-4 pb-14 pt-3">
          {view === "control" && (
            <div className="flex h-full min-h-0 flex-col gap-2">
              <div className="min-h-0 flex-none">
                <DeviceStatus />
              </div>
              <ChannelControl />
              <PresetPanel />
            </div>
          )}
          {view === "pair" && <PairView />}
          {view === "settings" && <SettingsView />}
        </main>
      </div>
      <BottomBar />
      <NoticeToast />
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
