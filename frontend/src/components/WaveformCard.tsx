import { useApp } from "../store";

/**
 * 实时波形卡：显示 A/B 通道当前在播的波形名与状态。
 * 波形形状演示暂关（样式不理想，后续版本重做后再补回绘制）。
 */
export default function WaveformCard() {
  const s = useApp((st) => st.state);
  const lastPreset = useApp((st) => st.lastPreset);

  const presetOf = (ch: "A" | "B") =>
    s?.presets?.find((p) => p.name === lastPreset[ch]) ?? s?.presets?.[0] ?? null;
  const pulsingA = !!s?.pulse_active?.A;
  const pulsingB = !!s?.pulse_active?.B;

  const legend = (ch: "A" | "B", presetName: string | null, pulsing: boolean, dot: string) => (
    <span className="flex items-center gap-1 text-[11px] text-muted">
      <span className="h-2 w-2 flex-none rounded-full" style={{ background: dot }} />
      <span>{ch}</span>
      <span className="max-w-[8rem] truncate">{presetName ?? "未选择波形"}</span>
      {pulsing && <span className="text-[10px] text-faint">播放中</span>}
    </span>
  );

  return (
    <div className="flex min-h-0 flex-col rounded-[14px] border border-line bg-panel p-3">
      <div className="mb-1.5 flex flex-none items-center justify-between gap-2">
        <h3 className="text-[12px] font-semibold tracking-[1.5px] text-muted">实时波形</h3>
        <div className="flex items-center gap-3">
          {legend("A", presetOf("A")?.name ?? null, pulsingA, "#f7d97a")}
          {legend("B", presetOf("B")?.name ?? null, pulsingB, "#4fc3f7")}
        </div>
      </div>
      <div className="flex min-h-0 w-full flex-1 items-center justify-center rounded-lg border border-line bg-ink3">
        <span className="text-[12px] text-faint">波形演示后续版本提供</span>
      </div>
    </div>
  );
}
