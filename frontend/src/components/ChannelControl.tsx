import { useEffect, useState } from "react";
import { Link2, Minus, Pause, Play, Plus, Square } from "lucide-react";
import { run, targets } from "../commands";
import { api } from "../api";
import { useApp } from "../store";

export default function ChannelControl() {
  const s = useApp((st) => st.state);
  const focusCh = useApp((st) => st.focusCh);
  const linkOn = useApp((st) => st.linkOn);
  const toggleLink = useApp((st) => st.toggleLink);
  const setFocus = useApp((st) => st.setFocus);
  const lastPreset = useApp((st) => st.lastPreset);
  // 窄窗口时 A/B 卡竖排，避免挤压
  const [compact, setCompact] = useState(window.innerWidth < 1150);
  useEffect(() => {
    const onResize = () => setCompact(window.innerWidth < 1150);
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  const capOf = (ch: "A" | "B") => s?.effective_caps?.[ch] ?? 100;

  return (
    <div className="mb-0 flex min-h-0 flex-1 flex-col rounded-[14px] border border-line bg-panel p-3">
      <h3 className="mb-2 flex-none text-[12px] font-semibold tracking-[1.5px] text-muted">A / B 双通道</h3>
      <div
        className={`grid min-h-0 flex-1 items-stretch gap-2 ${
          compact ? "grid-cols-1" : "grid-cols-[1fr_56px_1fr]"
        }`}
      >
        <ChannelCard ch="A" focus={focusCh === "A"} cap={capOf("A")} onFocus={() => setFocus("A")} preset={lastPreset.A} />
        {!compact && (
          <div className="flex items-center justify-center">
            <button
              onClick={toggleLink}
              title="A/B 联动"
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
  const s = useApp((st) => st.state);
  const cur = s?.current?.[ch] ?? 0;
  const pulsing = !!s?.pulse_active?.[ch];
  const req = s?.requested?.[ch];
  const dev = s?.device_channels?.[ch];
  const devLabel = dev?.name ? `${dev.name}${dev.location ? " · " + dev.location : ""}` : "未设置";
  const active = s?.active_channels?.[ch];
  const chanOn = s?.enabled_channels?.[ch] ?? true;
  const pattern = s?.patterns?.[ch] ?? null;
  const [slide, setSlide] = useState(cur);
  useEffect(() => setSlide(cur), [cur]);

  const commit = () => run("hold_strength", { value: slide }, targets(ch));

  const toggleChan = async () => {
    try {
      await api.setChannelEnabled(ch, !chanOn);
    } catch {
      /* 状态由 ws 推送刷新 */
    }
  };

  // AI 强度修正倍率滑杆：50%~150%（只乘 AI 的强度动作）
  const scale = s?.strength_scale?.[ch] ?? 1.0;
  const [scaleDraft, setScaleDraft] = useState(scale);
  useEffect(() => setScaleDraft(scale), [scale]);

  const commitScale = async () => {
    const v = Math.round(scaleDraft * 100) / 100;
    if (Math.abs(v - scale) < 0.005) return;
    try {
      await api.setChannelScale(ch, v);
    } catch {
      /* 状态由 ws 推送刷新 */
    }
  };

  return (
    <div
      onClick={onFocus}
      className={`flex cursor-pointer flex-col justify-between gap-1 rounded-[12px] border-2 bg-panel2 p-2.5 transition-colors ${
        chanOn ? (focus ? "border-line2" : "border-line") : "border-bad/40 opacity-60"
      }`}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="flex min-w-0 flex-1 items-center gap-1.5 text-[15px] font-bold">
          <span className="flex-none">{ch} 通道</span>
          <span className="truncate text-[12px] font-semibold text-accent">{dev?.name ?? "未设置"}</span>
        </span>
        <button
          onClick={(e) => {
            e.stopPropagation();
            void toggleChan();
          }}
          title={chanOn ? `关闭 ${ch} 通道` : `开启 ${ch} 通道`}
          className={`h-7 w-9 flex-none shrink-0 rounded-[8px] border text-[12px] font-semibold leading-none transition-colors ${
            chanOn
              ? "border-line bg-panel2 text-muted hover:text-text"
              : "border-bad/60 bg-bad/20 text-bad"
          }`}
        >
          {chanOn ? "开" : "关"}
        </button>
      </div>
      <div className="flex items-baseline justify-between">
        <div className={`text-[24px] font-bold leading-tight ${pulsing ? "text-accent" : ""}`}>
          {cur}
          <small className="text-[12px] font-normal text-muted"> / {cap}</small>
          {req !== null && req !== undefined && req !== cur && (
            <small className="text-[12px] font-normal text-warn"> 设定{req}</small>
          )}
        </div>
        <span className="text-[11px] text-muted">
          {!chanOn ? "已关闭" : active ? (pulsing ? "▶ " + (pattern ?? preset ?? "播放中") : "工作中") : "未工作"}
        </span>
      </div>
      <div className="truncate text-[11px] text-faint" title={devLabel}>
        {dev?.location ? `位置：${dev.location}` : "位置未设置"}
      </div>
      {/* AI 强度修正倍率滑杆：50%~150% */}
      <div className="flex items-center gap-1.5" onClick={(e) => e.stopPropagation()}>
        <span className="flex-none text-[11px] text-muted">强度修正</span>
        <input
          type="range"
          min={0.5}
          max={1.5}
          step={0.05}
          value={scaleDraft}
          disabled={!chanOn}
          onChange={(e) => setScaleDraft(Number(e.target.value))}
          onPointerUp={() => void commitScale()}
          onKeyUp={() => void commitScale()}
          className="min-w-0 flex-1 disabled:opacity-40"
        />
        <span
          className={`w-11 flex-none text-right text-[11px] font-semibold tabular-nums ${
            Math.abs(scaleDraft - 1.0) > 0.005 ? "text-accent" : "text-muted"
          }`}
        >
          ×{Math.round(scaleDraft * 100)}%
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
        <Btn icon={<Minus size={14} />} label="" title={`${ch} 减弱`} onClick={() => run("add_strength", { delta: -10 }, targets(ch))} />
        <Btn icon={<Plus size={14} />} label="" title={`${ch} 增强`} onClick={() => run("add_strength", { delta: 10 }, targets(ch))} />
        <Btn
          icon={pulsing ? <Pause size={14} /> : <Play size={14} />}
          label={pulsing ? "暂停" : "播放"}
          onClick={async () => {
            if (pulsing) await run("clear", {}, [ch]);
            else {
              const p = preset ?? useApp.getState().state?.presets?.[0]?.name;
              if (p) await run("pulse_hold", { pattern: p }, targets(ch));
            }
          }}
        />
        <Btn icon={<Square size={14} />} label="停止" danger onClick={() => run("clear", {}, targets(ch))} />
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
  return (
    <button
      title={title}
      onClick={onClick}
      className={`flex items-center gap-1 rounded-[10px] border px-3 py-1.5 text-xs transition-colors ${
        accent
          ? "border-transparent bg-accent font-semibold text-ink"
          : danger
            ? "border-bad/50 text-bad hover:bg-bad/10"
            : "border-line bg-panel2 hover:border-line2"
      }`}
    >
      {icon}
      {label}
    </button>
  );
}
