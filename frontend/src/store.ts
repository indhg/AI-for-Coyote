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
}
export const useChat = create<ChatStore>((set) => ({
  messages: [],
  busy: false,
  push: (m) => set((st) => ({ messages: [...st.messages, m] })),
  setBusy: (b) => set({ busy: b }),
}));

// ---------- 布局（三栏宽度，可拖拽调节，持久化） ----------
function readW(key: string, fallback: number): number {
  try {
    const v = Number(localStorage.getItem(key));
    if (Number.isFinite(v) && v > 0) return v;
  } catch {
    /* ignore */
  }
  return fallback;
}
interface LayoutStore {
  sidebarW: number;
  chatW: number;
  setSidebarW: (w: number) => void;
  setChatW: (w: number) => void;
}
export const useLayout = create<LayoutStore>((set) => ({
  sidebarW: readW("layout.sidebarW", 260),
  chatW: readW("layout.chatW", 560),
  setSidebarW: (w) => {
    try {
      localStorage.setItem("layout.sidebarW", String(w));
    } catch {
      /* ignore */
    }
    set({ sidebarW: w });
  },
  setChatW: (w) => {
    try {
      localStorage.setItem("layout.chatW", String(w));
    } catch {
      /* ignore */
    }
    set({ chatW: w });
  },
}));
