import { useEffect, useRef, useState } from "react";
import TopBar, { type ViewName, type BoardName } from "./components/TopBar";
import Sidebar from "./components/Sidebar";
import DeviceStatus from "./components/DeviceStatus";
import ChannelControl from "./components/ChannelControl";
import PresetPanel from "./components/PresetPanel";
import BottomBar from "./components/BottomBar";
import ChatPanel from "./components/ChatPanel";
import DungeonPanel from "./components/DungeonPanel";
import NoticeToast from "./components/NoticeToast";
import OnboardingTour from "./components/OnboardingTour";
import { TOURS } from "./onboarding";
import { PairView, SettingsView, HelpView } from "./components/views";
import { api } from "./api";
import { useApp, useChat, useLayout } from "./store";
import { doEstop } from "./commands";
import { useT } from "./i18n";

/** 空格长按触发急停的时长（毫秒，与进度条动画同步） */
const ESTOP_HOLD_MS = 1000;

export default function App() {
  const t = useT();
  const [view, setView] = useState<ViewName>("control");
  const [board, setBoard] = useState<BoardName>("chat");
  // 进入地牢：默认关自动运行（传感器随之暂停）；不动摄像头/麦克风各自的开关状态，
  // 切回聊天后重开「自动运行」即可恢复
  useEffect(() => {
    if (board !== "dungeon") return;
    api.setAutopilot(false).catch(() => {});
  }, [board]);
  // 新手引导：先等公告处理完（或本版公告已看过），再按版本记忆显示引导 1；设置页可重看
  const [tourIdx, setTourIdx] = useState<number | null>(null);
  const [noticeHandled, setNoticeHandled] = useState(false);
  const [noticeForced, setNoticeForced] = useState(false); // 帮助里点「公告」→ 强制重弹
  const version = useApp((st) => st.state?.config_info?.version ?? "");
  useEffect(() => {
    if (!version) return;
    // 本版公告已看过 → 公告不会弹，直接放行引导
    let dismissed = false;
    try {
      dismissed = localStorage.getItem("notice_dismissed_version") === version;
    } catch {
      /* 非核心的公告记忆失败不影响引导流程 */
    }
    if (dismissed) {
      setNoticeHandled(true);
    }
  }, [version]);
  useEffect(() => {
    if (!version || !noticeHandled) return;
    const tour = TOURS[0];
    let done = false;
    try {
      done = localStorage.getItem(`tour_done_${tour.id}_${version}`) === "1";
    } catch {
      /* 非核心的新手引导记忆失败时按未完成处理 */
    }
    if (!done) {
      const t = window.setTimeout(() => setTourIdx(0), 800);
      return () => window.clearTimeout(t);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [version, noticeHandled]);
  // 首启保护：新手引导未完成时，若后端还停在模拟测试态（上次会话遗留 / 端口复用旧实例），
  // 先退出测试，避免「一打开就在测试、自动开场顶掉引导配对步骤」（2026-09-03 用户反馈）；
  // 想试玩随时可点「点击进入测试（模拟设备）」。
  useEffect(() => {
    if (!version) return;
    const tour = TOURS[0];
    let done = false;
    try {
      done = localStorage.getItem(`tour_done_${tour.id}_${version}`) === "1";
    } catch {
      /* 默认未完成 → 走退出逻辑 */
    }
    if (done) return;
    if (useApp.getState().state?.test_mode) {
      void api.testMode(false).catch(() => {});
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [version]);
  const sidebarW = useLayout((s) => s.sidebarW);
  const controlW = useLayout((s) => s.controlW);
  const mode = useLayout((s) => s.mode);
  const updateLayout = useLayout((s) => s.updateLayout);
  // 中/窄屏：抽屉开关（右=设备/配对/设置视图；左=角色卡与入口，仅窄屏用）
  const [rightOpen, setRightOpen] = useState(false);
  const [leftOpen, setLeftOpen] = useState(false);
  useEffect(() => {
    if (mode === "wide") {
      setRightOpen(false);
      setLeftOpen(false);
    }
  }, [mode]);
  // 全局缩放：宽/中屏按窗口宽度缩放（0.8~1.3）；窄屏关闭缩放，靠抽屉布局保证可读可用
  const [zoom, setZoom] = useState(1);
  useEffect(() => {
    const calc = () => {
      const w = window.innerWidth;
      setZoom(w < 800 ? 1 : Math.min(1.3, Math.max(0.8, w / 1600)));
      updateLayout(); // 三栏比例 + 布局档位随窗口宽度重算
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
        // 语言记忆同步：localStorage 里存过 中/EN 且与后端不一致时补一次切换
        let saved: string | null = null;
        try {
          saved = localStorage.getItem("lang");
        } catch {
          /* 记忆失败不阻塞 */
        }
        if (saved && (saved === "zh" || saved === "en") && s.lang && saved !== s.lang) {
          void api.setLang(saved as "zh" | "en").catch(() => {});
        }
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
      <TopBar view={view} onView={setView} board={board} onBoard={setBoard} />
      {(() => {
        const cols =
          mode === "wide"
            ? `${sidebarW}px 1fr ${controlW}px`
            : mode === "mid"
              ? `${sidebarW}px 1fr 0`
              : `0 1fr 0`;
        const rightView = (
          <main className="min-h-0 overflow-y-auto border-l border-line px-4 pb-14 pt-3">
            {view === "control" && (
              <div className="flex h-full min-h-0 flex-col gap-2">
                <div className="min-h-0 flex-none">
                  <DeviceStatus />
                </div>
                <ChannelControl />
                {board !== "dungeon" && <PresetPanel />}
              </div>
            )}
            {view === "pair" && <PairView />}
            {view === "settings" && <SettingsView />}
            {view === "help" && (
              <HelpView
                onReplayTour={() => setTourIdx(0)}
                onShowNotice={() => setNoticeForced(true)}
              />
            )}
          </main>
        );
        return (
          <div
            className="relative grid h-full min-h-0 flex-1"
            style={{ gridTemplateColumns: cols, gridTemplateRows: "minmax(0, 1fr)" }}
          >
            {mode !== "narrow" && <Sidebar view={view} onView={setView} board={board} />}
            <div className="h-full min-h-0">{board === "chat" ? <ChatPanel /> : <DungeonPanel />}</div>
            {mode === "wide" && rightView}
            {/* 中/窄屏右抽屉：设备/配对/设置/帮助 */}
            {mode !== "wide" && rightOpen && (
              <div className="absolute inset-y-0 right-0 z-30 flex w-[min(420px,92vw)] flex-col border-l border-line bg-ink2">
                <div className="flex flex-none items-center justify-between border-b border-line px-3 py-1.5">
                  <span className="text-[12px] font-semibold text-muted">{t("设备 / 视图")}</span>
                  <button
                    onClick={() => setRightOpen(false)}
                    className="rounded-md border border-line bg-panel2 px-2 py-0.5 text-[11px] text-muted transition-colors hover:border-line2 hover:text-text"
                  >
                    {t("收起 ✕")}                  </button>
                </div>
                <div className="min-h-0 flex-1">{rightView}</div>
              </div>
            )}
            {/* 窄屏左抽屉：角色卡 / 入口导航 */}
            {mode === "narrow" && leftOpen && (
              <div className="absolute inset-y-0 left-0 z-30 flex w-[min(320px,90vw)] flex-col border-r border-line bg-ink2">
                <div className="flex flex-none items-center justify-between border-b border-line px-3 py-1.5">
                  <span className="text-[12px] font-semibold text-muted">{t("角色 / 入口")}</span>
                  <button
                    onClick={() => setLeftOpen(false)}
                    className="rounded-md border border-line bg-panel2 px-2 py-0.5 text-[11px] text-muted transition-colors hover:border-line2 hover:text-text"
                  >
                    {t("收起 ✕")}                  </button>
                </div>
                <div className="min-h-0 flex-1 overflow-y-auto">
                  <Sidebar view={view} onView={setView} board={board} />
                </div>
              </div>
            )}
            {/* 中/窄屏浮动开关 */}
            {mode !== "wide" && (
              <div className="absolute inset-y-0 right-0 z-40 flex items-center">
                <button
                  onClick={() => setRightOpen((o) => !o)}
                  title={rightOpen ? t("收起设备面板") : t("打开设备面板")}
                  className="rounded-l-md border border-r-0 border-line bg-ink2 px-1.5 py-3 text-[13px] text-muted transition-colors hover:text-accent"
                >
                  {rightOpen ? "›" : "‹"}
                </button>
              </div>
            )}
            {mode === "narrow" && (
              <div className="absolute inset-y-0 left-0 z-40 flex items-center">
                <button
                  onClick={() => setLeftOpen((o) => !o)}
                  title={leftOpen ? t("收起角色面板") : t("打开角色面板")}
                  className="rounded-r-md border border-l-0 border-line bg-ink2 px-1.5 py-3 text-[13px] text-muted transition-colors hover:text-accent"
                >
                  {leftOpen ? "«" : "»"}
                </button>
              </div>
            )}
          </div>
        );
      })()}
      <BottomBar />
      <NoticeToast
        force={noticeForced}
        onDismissed={() => {
          setNoticeHandled(true);
          setNoticeForced(false);
        }}
      />
      {tourIdx !== null && TOURS[tourIdx] && (
        <OnboardingTour
          tour={TOURS[tourIdx]}
          view={view}
          onView={setView}
          onFinish={() => {
            const tour = TOURS[tourIdx];
            if (tour) {
              try {
                localStorage.setItem(`tour_done_${tour.id}_${version}`, "1");
              } catch {
                /* 非核心记忆失败不影响结束引导 */
              }
            }
            setTourIdx(null);
          }}
        />
      )}
      {holding && (
        <div className="pointer-events-none fixed inset-x-0 bottom-20 z-50 flex justify-center">
          <div className="w-64 rounded-[10px] border border-line bg-panel2 px-4 py-3 shadow-lg">
            <div className="flex items-baseline justify-between">
              <span className="text-sm font-semibold text-text">{t("「急停中…」")}</span>
              <span className="text-xs text-muted">{t("松开取消")}</span>
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
