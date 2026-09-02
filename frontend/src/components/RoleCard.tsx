import { useEffect, useRef, useState } from "react";
import { Check, ChevronDown, ChevronUp } from "lucide-react";
import { api } from "../api";
import { useApp } from "../store";
import {
  ENTRIES,
  INTENSITY_BADGE_CLS,
  INTENSITY_DOT_CLS,
  INTENSITY_LEVELS,
  ENTRY_RING_ACTIVE_CLS,
  ENTRY_RING_CLS,
  entryAvatar,
  entryOf,
  type Entry,
} from "../roleTheme";

// 体验版「新手推荐」角标：点过一次后不再显示（本地记忆）
const TRIAL_BADGE_KEY = "trial_badge_seen";

// 侧边栏顶部的「当前入口卡」：显示当前角色一行；点开浮动小下拉——上段列入口（体验版/角色），下段强度三档
export default function RoleCard() {
  const role = useApp((st) => st.state?.role ?? "触手");
  const profile = useApp((st) => st.state?.profile ?? "纯爱");
  const intensity = useApp((st) => st.state?.intensity_level ?? "中");
  const [open, setOpen] = useState(false);
  const [listStep, setListStep] = useState(false); // 展开入口列表
  const [err, setErr] = useState("");
  const [trialSeen, setTrialSeen] = useState(() => {
    try {
      return window.localStorage.getItem(TRIAL_BADGE_KEY) === "1";
    } catch {
      return false;
    }
  });
  const rootRef = useRef<HTMLDivElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const rowRef = useRef<HTMLButtonElement>(null);

  const current = entryOf(role, profile);

  // 点外部关闭下拉
  useEffect(() => {
    if (!open) return;
    const onDown = (ev: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(ev.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  // 入口列表展开时：点列表外任意处收起列表（浮层本身保持打开，强度三档位置不动）
  useEffect(() => {
    if (!open || !listStep) return;
    const onDown = (ev: MouseEvent) => {
      if (listRef.current && !listRef.current.contains(ev.target as Node)) {
        if (rowRef.current && rowRef.current.contains(ev.target as Node)) return;
        setListStep(false);
      }
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open, listStep]);

  const switchEntry = async (e: Entry) => {
    setErr("");
    const already = e.role === role && e.profile === profile;
    // 点过体验版（或任意入口都算见过引导）→ 新手角标消失
    if (!trialSeen) {
      try {
        window.localStorage.setItem(TRIAL_BADGE_KEY, "1");
      } catch {
        /* 非核心的新手角标记忆失败不影响切换入口 */
      }
      setTrialSeen(true);
    }
    if (already) {
      setListStep(false);
      return;
    }
    try {
      await api.setProfile(e.role, e.profile);
      setListStep(false);
    } catch (ex) {
      setErr(`切换失败：${(ex as Error).message}`);
    }
  };

  const switchIntensity = async (lv: string) => {
    if (lv === intensity) return;
    setErr("");
    try {
      await api.setIntensity(lv);
    } catch (ex) {
      setErr(`强度档切换失败：${(ex as Error).message}`);
    }
  };

  return (
    <div ref={rootRef} className="relative mb-3.5 rounded-[14px] border border-line bg-panel p-3.5">
      <button
        className="flex w-full items-center gap-2.5 text-left"
        onClick={() => setOpen((v) => (v ? false : (setListStep(false), true)))}
        title="切换角色入口与电击强度"
      >
        <span
          className={`relative flex h-9 w-9 flex-none items-center justify-center overflow-hidden rounded-[10px] border text-[16px] font-bold ${
            ENTRY_RING_ACTIVE_CLS[current?.key ?? ""] ?? "border-line2 bg-accent/15"
          }`}
        >
          {entryAvatar(current?.key ?? "") ? (
            <img
              src={entryAvatar(current?.key ?? "")!}
              alt={current?.label ?? role}
              className="h-full w-full object-cover"
            />
          ) : (
            (current?.label ?? role).slice(0, 1)
          )}
        </span>
        <span className="min-w-0 flex-1">
          <span className="flex items-center gap-1.5 text-[14px] font-semibold">
            {current?.label ?? role}
            {current?.recommended && (
              <span className="flex-none rounded-md border border-accent/60 bg-accent/15 px-1.5 py-px text-[10px] font-bold text-accent">
                推荐
              </span>
            )}
            {current?.trial && !trialSeen && (
              <span className="flex-none rounded-md bg-accent px-1.5 py-px text-[10px] font-bold text-ink">
                新手推荐
              </span>
            )}
          </span>
          <span className="mt-0.5 flex items-center gap-1 text-[11px] text-muted">
            <span
              className={`h-1.5 w-1.5 flex-none rounded-full ${INTENSITY_DOT_CLS[intensity] ?? ""}`}
            />
            强度 · {intensity}
          </span>
        </span>
        {open ? (
          <ChevronUp size={14} className="flex-none text-faint" />
        ) : (
          <ChevronDown size={14} className="flex-none text-faint" />
        )}
      </button>

      {open && (
        <div className="absolute left-0 right-0 top-full z-30 mt-2 rounded-[12px] border border-line bg-panel shadow-xl shadow-black/50">
          <div className="flex flex-col gap-2 p-3">
            <div className="relative flex flex-col gap-0.5">
              <span className="px-1 text-[10px] font-medium tracking-wide text-muted">角色入口</span>
              <button
                ref={rowRef}
                onClick={() => setListStep((v) => !v)}
                className="flex items-center gap-2 rounded-[6px] px-2 py-1.5 text-left text-[12px] transition-colors hover:bg-panel2"
                title="展开入口列表"
              >
                <span className="flex-1 text-text">
                  {current?.label ?? role}
                  <span className="ml-1 text-[10px] text-muted">（点击换入口）</span>
                </span>
                {listStep ? (
                  <ChevronUp size={12} className="flex-none text-faint" />
                ) : (
                  <ChevronDown size={12} className="flex-none text-faint" />
                )}
              </button>
              {listStep && (
                <div
                  ref={listRef}
                  className="absolute left-0 right-0 top-full z-40 mt-1 flex flex-col gap-0.5 rounded-[8px] border border-line bg-panel p-1 shadow-xl shadow-black/60"
                >
                  {ENTRIES.map((e) => {
                    const active = e.role === role && e.profile === profile;
                    return (
                      <button
                        key={e.key}
                        onClick={() => void switchEntry(e)}
                        className={`flex items-center gap-2 rounded-[6px] border px-2 py-1.5 text-left text-[12px] transition-all ${
                          active
                            ? `${ENTRY_RING_ACTIVE_CLS[e.key] ?? "border-line2 bg-accent/15"} font-medium text-text scale-[1.03]`
                            : `border-transparent font-medium text-text hover:bg-panel2 hover:scale-[1.03] ${ENTRY_RING_CLS[e.key] ?? ""}`
                        }`}
                      >
                        <span className="flex h-5 w-5 flex-none items-center justify-center overflow-hidden rounded-[5px]">
                          {entryAvatar(e.key) ? (
                            <img src={entryAvatar(e.key)!} alt={e.label} className="h-full w-full object-cover" />
                          ) : (
                            <span className="text-[10px] font-bold">{e.label.slice(0, 1)}</span>
                          )}
                        </span>
                        <span className="min-w-0 flex-1">{e.label}</span>
                        {e.recommended && (
                          <span className="flex-none rounded border border-accent/40 px-1 py-px text-[9px] font-bold text-accent">
                            推荐
                          </span>
                        )}
                        {e.trial && !trialSeen && (
                          <span className="flex-none rounded bg-accent/15 px-1 py-px text-[9px] font-bold text-accent">
                            新手推荐
                          </span>
                        )}
                        {active && <Check size={12} className="flex-none text-accent" />}
                      </button>
                    );
                  })}
                </div>
              )}
            </div>

            <div className="flex flex-col gap-0.5">
              <div className="flex items-center justify-between px-1">
                <span className="text-[10px] font-medium tracking-wide text-muted">强度</span>
                <span
                  className={`rounded-md border px-1.5 py-px text-[10px] ${INTENSITY_BADGE_CLS[intensity] ?? INTENSITY_BADGE_CLS["中"]}`}
                >
                  当前 ×{INTENSITY_SCALE_TEXT[intensity] ?? 1}
                </span>
              </div>
              <div className="grid grid-cols-3 gap-1">
                {INTENSITY_LEVELS.map((lv) => {
                  const selected = lv === intensity;
                  return (
                    <button
                      key={lv}
                      onClick={() => void switchIntensity(lv)}
                      className={`flex items-center justify-center gap-1.5 rounded-[6px] border px-1 py-1.5 text-[12px] transition-colors ${
                        selected
                          ? "border-accent bg-accent font-semibold text-ink"
                          : "border-line bg-panel2 font-medium text-text hover:border-line2"
                      }`}
                    >
                      <span
                        className={`h-1.5 w-1.5 flex-none rounded-full ${
                          selected ? "bg-ink" : (INTENSITY_DOT_CLS[lv] ?? "bg-faint")
                        }`}
                      />
                      {lv}
                    </button>
                  );
                })}
              </div>
            </div>

            {err && <p className="text-[10px] leading-relaxed text-red-400">{err}</p>}
          </div>
        </div>
      )}
    </div>
  );
}

const INTENSITY_SCALE_TEXT: Record<string, string> = { 轻: "0.7", 中: "1.0", 重: "1.3" };
