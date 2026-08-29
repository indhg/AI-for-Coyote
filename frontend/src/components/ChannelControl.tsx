import { useEffect, useState } from "react";
import { Link2, Minus, Pause, Play, Plus, Square } from "lucide-react";
import { run, targets } from "../commands";
import { api } from "../api";
import { useApp, useLayout } from "../store";

export default function ChannelControl() {
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
      <h3 className="mb-2 flex-none text-[12px] font-semibold tracking-[1.5px] text-muted">A / B 双通道</h3>
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

  return (
    <div
      onClick={onFocus}
      className={`flex cursor-pointer flex-col justify-start gap-0.5 rounded-[12px] border-2 bg-panel2 p-2 transition-colors ${
        chanOn ? (focus ? "border-line2" : "border-line") : "border-bad/40 opacity-60"
      }`}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="flex min-w-0 flex-1 items-center gap-1.5 text-[13px] font-bold">
          <span className="flex-none">{ch} 通道</span>
          <span className="truncate text-[11px] font-semibold text-accent">{dev?.name ?? "未设置"}</span>
        </span>
        <button
          onClick={(e) => {
            e.stopPropagation();
            void toggleChan();
          }}
          title={chanOn ? `关闭 ${ch} 通道` : `开启 ${ch} 通道`}
          className={`h-6 w-8 flex-none shrink-0 rounded-[6px] border text-[11px] font-semibold leading-none transition-colors ${
            chanOn
              ? "border-line bg-panel2 text-muted hover:text-text"
              : "border-bad/60 bg-bad/20 text-bad"
          }`}
        >
          {chanOn ? "开" : "关"}
        </button>
      </div>
      <div className="flex items-baseline justify-between">
        <div className={`text-[20px] font-bold leading-tight ${pulsing ? "text-accent" : ""}`}>
          {cur}
          <small className="text-[11px] font-normal text-muted"> / {cap}</small>
          {req !== null && req !== undefined && req !== cur && (
            <small className="text-[11px] font-normal text-warn"> 设定{req}</small>
          )}
        </div>
        <span className="text-[10px] text-muted">
          {!chanOn ? "已关闭" : active ? (pulsing ? "▶ " + (pattern ?? preset ?? "播放中") : "工作中") : "未工作"}
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
        <Btn icon={<Minus size={12} />} label="" title={`${ch} 减弱`} onClick={() => run("add_strength", { delta: -10 }, targets(ch))} />
        <Btn icon={<Plus size={12} />} label="" title={`${ch} 增强`} onClick={() => run("add_strength", { delta: 10 }, targets(ch))} />
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
  return (
    <button
      title={title}
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
      {label}
    </button>
  );
}
