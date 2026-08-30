import { create } from "zustand";
import type { FullState } from "./types";

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

interface LayoutStore {
  sidebarW: number;
  controlW: number;
  updateLayout: () => void;
}
export const useLayout = create<LayoutStore>((set) => ({
  sidebarW: calcSidebarW(),
  controlW: calcControlW(),
  updateLayout: () => set({ sidebarW: calcSidebarW(), controlW: calcControlW() }),
}));
