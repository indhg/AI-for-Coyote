import { useApp } from "../store";

function Seg({
  k,
  v,
  valueClass = "text-[14px]",
  accent = false,
}: {
  k?: string;
  v: string;
  valueClass?: string;
  accent?: boolean;
}) {
  return (
    <span className="flex min-w-0 items-baseline gap-1">
      {k && <span className="flex-none text-[11px] text-muted">{k}</span>}
      <span
        className={`truncate font-semibold leading-tight ${valueClass} ${accent ? "text-accent" : ""}`}
        title={v}
      >
        {v}
      </span>
    </span>
  );
}

export default function DeviceStatus() {
  const s = useApp((st) => st.state);
  const st = s?.relay?.status ?? "disconnected";
  const paired = st === "paired";
  const waveOf = (ch: "A" | "B") =>
    !s?.pulse_active?.[ch] ? "空闲" : s?.patterns?.[ch] ?? "播放中";
  // 音量显示：相对「惨叫档」的百分比（后端 level_pct；旧版无此字段时回退原始电平×100）
  const audioPct = s?.audio?.running
    ? Math.max(0, Math.min(100, s.audio.level_pct ?? Math.round((s.audio.level ?? 0) * 100)))
    : 0;
  const acc = (ch: "A" | "B") => {
    const d = s?.device_channels?.[ch];
    const name = d?.name ?? "未设置";
    const loc = d?.location?.trim();
    return loc ? `${name} · ${loc}` : name;
  };

  return (
    <div className="flex min-h-0 flex-col rounded-[14px] border border-line bg-panel p-3">
      <h3 className="mb-2 flex-none text-[12px] font-semibold tracking-[1.5px] text-muted">设备状态</h3>
      <div className="flex min-h-0 flex-1 flex-col gap-1.5">
        {/* 第一行：连接 + 麦克风（音量条常驻，未开启时显示空条） */}
        <div className="grid grid-cols-[1fr_auto] items-center gap-3 rounded-xl border border-line bg-panel2 px-4 py-2">
          <Seg k="连接" v={paired ? "已连接" : "未连接"} />
          <span className="flex items-center gap-2">
            <span className="flex-none text-[11px] text-muted">麦克风</span>
            <div className="h-[8px] w-24 flex-none overflow-hidden rounded-full bg-ink3">
              <div
                className="h-full rounded-full bg-accent transition-all"
                style={{ width: `${audioPct}%` }}
              />
            </div>
            <span className="w-6 flex-none text-right text-[12px] font-semibold tabular-nums">
              {audioPct}
            </span>
            <span className="w-24 flex-none truncate text-[11px] text-faint">
              {s?.audio?.running ? s.audio.last_text || "监听中…" : "未开启"}
            </span>
          </span>
        </div>
        {/* A/B 通道行：固定列宽网格，两行各列严格对齐 */}
        {(["A", "B"] as const).map((ch) => (
          <div
            key={ch}
            className="grid grid-cols-[3rem_5.5rem_6.5rem_1fr] items-baseline gap-3 rounded-xl border border-line bg-panel2 px-4 py-2"
          >
            <span className="text-[13px] font-bold">{ch} 通道</span>
            <Seg k="强度" v={`${s?.current[ch] ?? 0} / ${s?.effective_caps?.[ch] ?? 100}`} accent />
            <Seg k="波形" v={waveOf(ch)} />
            <Seg v={acc(ch)} valueClass="text-[13px]" />
          </div>
        ))}
      </div>
    </div>
  );
}
