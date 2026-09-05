import { create } from "zustand";
import type { DungeonRender, FullState } from "./types";

// ---------- 应用状态（与后端实时状态同步） ----------
interface AppStore {
  state: FullState | null;
  focusCh: "A" | "B";
  linkOn: boolean;
  lastPreset: Record<"A" | "B", string | null>;
  setState: (s: FullState) => void;
  setFocus: (ch: "A" | "B") => void;
  toggleLink: () => void;
  setLastPreset: (ch: "A" | "B", name: string) => void;
}
export const useApp = create<AppStore>((set) => ({
  state: null,
  focusCh: "A",
  linkOn: false,
  lastPreset: { A: null, B: null },
  setState: (s) => set({ state: s }),
  setFocus: (ch) => set({ focusCh: ch }),
  toggleLink: () => set((st) => ({ linkOn: !st.linkOn })),
  setLastPreset: (ch, name) =>
    set((st) => ({ lastPreset: { ...st.lastPreset, [ch]: name } })),
}));

// ---------- 聊天记录 ----------
export interface ChatMsg {
  role: "user" | "ai" | "sys";
  text: string;
  actions?: string;
}
interface ChatStore {
  messages: ChatMsg[];
  busy: boolean;
  push: (m: ChatMsg) => void;
  setBusy: (b: boolean) => void;
  clear: () => void;
}
export const useChat = create<ChatStore>((set) => ({
  messages: [],
  busy: false,
  push: (m) => set((st) => ({ messages: [...st.messages, m] })),
  setBusy: (b) => set({ busy: b }),
  clear: () => set({ messages: [] }),
}));

// ---------- 布局（三栏固定比例，随窗口宽度计算，不可拖拽） ----------
function calcSidebarW(): number {
  try {
    const w = window.innerWidth;
    if (Number.isFinite(w) && w > 0) return Math.min(360, Math.max(160, Math.round(w * 0.158)));
  } catch {
    /* ignore */
  }
  return 268;
}

function calcControlW(): number {
  try {
    const w = window.innerWidth;
    if (Number.isFinite(w) && w > 0) return Math.min(900, Math.max(300, Math.round(w * 0.322)));
  } catch {
    /* ignore */
  }
  return 548;
}

/** 布局档位：宽 ≥1280 三栏；中 800-1279 聊天主栏 + 侧栏抽屉；窄 <800 单列 + 抽屉保安全操作 */
export type LayoutMode = "wide" | "mid" | "narrow";
function calcMode(): LayoutMode {
  try {
    const w = window.innerWidth;
    if (Number.isFinite(w) && w > 0) {
      if (w >= 1280) return "wide";
      if (w >= 800) return "mid";
      return "narrow";
    }
  } catch {
    /* ignore */
  }
  return "wide";
}

interface LayoutStore {
  sidebarW: number;
  controlW: number;
  mode: LayoutMode;
  updateLayout: () => void;
}
export const useLayout = create<LayoutStore>((set) => ({
  sidebarW: calcSidebarW(),
  controlW: calcControlW(),
  mode: calcMode(),
  updateLayout: () =>
    set({ sidebarW: calcSidebarW(), controlW: calcControlW(), mode: calcMode() }),
}));

// ---------- 地牢（紫金地牢） ----------
interface DungeonStore {
  render: DungeonRender | null;
  busy: boolean;
  error: string | null;
  notice: string | null;
  /** D30 路网：地图与岔口卡共享的「已选中待确认」节点；每帧 render 到达即清空 */
  selectedNodeId: string | null;
  /** D30 路网：mid/窄屏底部抽屉开合 */
  routeSheetOpen: boolean;
  setRender: (r: DungeonRender | null) => void;
  setBusy: (b: boolean) => void;
  setError: (e: string | null) => void;
  setNotice: (n: string | null) => void;
  setSelectedNodeId: (id: string | null) => void;
  setRouteSheetOpen: (o: boolean) => void;
}
export const useDungeon = create<DungeonStore>((set) => ({
  render: null,
  busy: false,
  error: null,
  notice: null,
  selectedNodeId: null,
  routeSheetOpen: false,
  setRender: (r) => set({ render: r, error: null, selectedNodeId: null, ...(r ? {} : { routeSheetOpen: false }) }),
  setBusy: (b) => set({ busy: b }),
  setError: (e) => set({ error: e }),
  setNotice: (n) => set({ notice: n }),
  setSelectedNodeId: (id) => set({ selectedNodeId: id }),
  setRouteSheetOpen: (o) => set({ routeSheetOpen: o }),
}));
