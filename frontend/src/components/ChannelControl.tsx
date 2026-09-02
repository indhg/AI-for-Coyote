import { useEffect, useRef, useState } from "react";
import { Link2, Minus, Pause, Play, Plus, Square } from "lucide-react";
import { run, targets } from "../commands";
import { api } from "../api";
import { useApp, useLayout } from "../store";
import { useT } from "../i18n";

export default function ChannelControl() {
  const t = useT();
  const s = useApp((st) => st.state);
  const focusCh = useApp((st) => st.focusCh);
  const linkOn = useApp((st) => st.linkOn);
  const toggleLink = useApp((st) => st.toggleLink);
  const setFocus = useApp((st) => st.setFocus);
  const lastPreset = useApp((st) => st.lastPreset);
  // 紧凑判断按右栏实际宽度（不是窗口宽）：仅极窄（<400px）才竖排，默认左右并排
  const controlW = useLayout((st) => st.controlW);
  const compact = controlW < 400;

  const capOf = (ch: "A" | "B") => s?.effective_caps?.[ch] ?? 100;

  return (
    <div className="mb-0 flex min-h-0 flex-none flex-col rounded-[14px] border border-line bg-panel p-3">
      <h3 className="mb-2 flex-none text-[12px] font-semibold tracking-[1.5px] text-muted">{t("A / B 双通道")}</h3>
      <div
        className={`grid items-start gap-2 ${
          compact ? "grid-cols-1" : "grid-cols-[1fr_56px_1fr]"
        }`}
      >
        <ChannelCard ch="A" focus={focusCh === "A"} cap={capOf("A")} onFocus={() => setFocus("A")} preset={lastPreset.A} />
        {!compact && (
          <div className="flex items-center justify-center">
            <button
              onClick={toggleLink}
              title={t("A/B 联动")}
              className={`h-[48px] w-[48px] rounded-[12px] border text-xl transition-colors ${
                linkOn ? "border-accent bg-accent text-ink" : "border-line bg-panel text-muted"
              }`}
            >
              <Link2 size={20} className="mx-auto" />
            </button>
          </div>
        )}
        <ChannelCard ch="B" focus={focusCh === "B"} cap={capOf("B")} onFocus={() => setFocus("B")} preset={lastPreset.B} />
      </div>
    </div>
  );
}

function ChannelCard({
  ch,
  focus,
  cap,
  onFocus,
  preset,
}: {
  ch: "A" | "B";
  focus: boolean;
  cap: number;
  onFocus: () => void;
  preset: string | null;
}) {
  const t = useT();
  const s = useApp((st) => st.state);
  const cur = s?.current?.[ch] ?? 0;
  const pulsing = !!s?.pulse_active?.[ch];
  const req = s?.requested?.[ch];
  const dev = s?.device_channels?.[ch];
  const active = s?.active_channels?.[ch];
  const chanOn = s?.enabled_channels?.[ch] ?? true;
  const pattern = s?.patterns?.[ch] ?? null;
  const [slide, setSlide] = useState(cur);
  useEffect(() => setSlide(cur), [cur]);
  // 上限浮窗：点「/ 上限」弹出滑杆（1~硬上限）
  const hardCap = s?.caps?.[ch] ?? 100;
  const [capOpen, setCapOpen] = useState(false);
  const [capDraft, setCapDraft] = useState(cap);
  const capRef = useRef<HTMLDivElement>(null);
  useEffect(() => setCapDraft(cap), [cap]);
  useEffect(() => {
    if (!capOpen) return;
    const onDown = (ev: MouseEvent) => {
      if (capRef.current && !capRef.current.contains(ev.target as Node)) setCapOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [capOpen]);

  const commitCap = async () => {
    const v = Math.max(1, Math.min(hardCap, Math.round(capDraft)));
    setCapDraft(v);
    if (v === cap) return;
    try {
      await api.setChannelCap(ch, v);
    } catch {
      /* 状态由 ws 推送刷新 */
    }
  };

  const commit = () => run("hold_strength", { value: slide }, targets(ch));

  const toggleChan = async () => {
    try {
      await api.setChannelEnabled(ch, !chanOn);
    } catch {
      /* 状态由 ws 推送刷新 */
    }
  };

  return (
    <div
      onClick={onFocus}
      className={`flex cursor-pointer flex-col justify-start gap-0.5 rounded-[12px] border-2 bg-panel2 p-2 transition-colors ${
        chanOn ? (focus ? "border-line2" : "border-line") : "border-bad/40 opacity-60"
      }`}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="flex min-w-0 flex-1 items-center gap-1.5 text-[13px] font-bold">
          <span className="flex-none">{t("{ch} 通道", { ch })}</span>
          <span className="truncate text-[11px] font-semibold text-accent">{t(dev?.name ?? "未设置")}</span>
        </span>
        <button
          onClick={(e) => {
            e.stopPropagation();
            void toggleChan();
          }}
          title={t(chanOn ? "关闭 {ch} 通道" : "开启 {ch} 通道", { ch })}
          className={`h-6 w-8 flex-none shrink-0 rounded-[6px] border text-[11px] font-semibold leading-none transition-colors ${
            chanOn
              ? "border-line bg-panel2 text-muted hover:text-text"
              : "border-bad/60 bg-bad/20 text-bad"
          }`}
        >
          {t(chanOn ? "开" : "关")}
        </button>
      </div>
      <div className="flex items-baseline justify-between">
        <div ref={capRef} className={`relative text-[20px] font-bold leading-tight ${pulsing ? "text-accent" : ""}`}>
          {cur}
          /
          <button
            onClick={() => setCapOpen((v) => !v)}
            title={t("调整该通道强度上限")}
            className="hover:text-accent"
          >
            {cap}
          </button>
          <span className="ml-1 align-middle text-[10px] font-normal text-faint">{t("上限可调")}</span>
          {req !== null && req !== undefined && req !== cur && (
            <small className="text-[11px] font-normal text-warn"> {t("设定{req}", { req })}</small>
          )}
          {capOpen && (
            <div className="absolute left-0 top-full z-40 mt-1 flex w-40 flex-col gap-1 rounded-[8px] border border-line bg-panel p-2 shadow-xl shadow-black/60">
              <span className="text-[10px] text-muted">{t("强度上限（1~{hardCap}）", { hardCap })}</span>
              <input
                type="range"
                min={1}
                max={hardCap}
                step={1}
                value={capDraft}
                onChange={(e) => setCapDraft(Number(e.target.value))}
                onPointerUp={() => void commitCap()}
                onKeyUp={() => void commitCap()}
                className="w-full"
              />
              <span className="text-right text-[11px] font-semibold tabular-nums text-accent">{capDraft}</span>
            </div>
          )}
        </div>
        <span className="text-[10px] text-muted">
          {!chanOn
            ? t("已关闭")
            : active
              ? pulsing
                ? "▶ " + t(pattern ?? preset ?? "播放中")
                : t("工作中")
              : t("未工作")}
        </span>
      </div>
      <input
        type="range"
        min={0}
        max={cap}
        value={slide}
        onChange={(e) => setSlide(Number(e.target.value))}
        onPointerUp={commit}
        onKeyUp={commit}
      />
      <div className="flex items-center justify-between gap-1">
        <Btn icon={<Minus size={12} />} label="" title={t("{ch} 减弱", { ch })} onClick={() => run("add_strength", { delta: -10 }, targets(ch))} />
        <Btn icon={<Plus size={12} />} label="" title={t("{ch} 增强", { ch })} onClick={() => run("add_strength", { delta: 10 }, targets(ch))} />
        <Btn
          icon={pulsing ? <Pause size={12} /> : <Play size={12} />}
          label={pulsing ? "暂停" : "播放"}
          onClick={async () => {
            if (pulsing) await run("clear", {}, [ch]);
            else {
              const p = preset ?? useApp.getState().state?.presets?.[0]?.name;
              if (p) await run("pulse_hold", { pattern: p }, targets(ch));
            }
          }}
        />
        <Btn icon={<Square size={12} />} label="停止" danger onClick={() => run("clear", {}, targets(ch))} />
      </div>
    </div>
  );
}

function Btn({
  icon,
  label,
  title,
  accent,
  danger,
  onClick,
}: {
  icon?: React.ReactNode;
  label: string;
  title?: string;
  accent?: boolean;
  danger?: boolean;
  onClick: () => void;
}) {
  const t = useT();
  return (
    <button
      title={title ? t(title) : undefined}
      onClick={onClick}
      className={`flex items-center gap-1 rounded-[8px] border px-2 py-1 text-[11px] transition-colors ${
        accent
          ? "border-transparent bg-accent font-semibold text-ink"
          : danger
            ? "border-bad/50 text-bad hover:bg-bad/10"
            : "border-line bg-panel2 hover:border-line2"
      }`}
    >
      {icon}
      {t(label)}
    </button>
  );
}
