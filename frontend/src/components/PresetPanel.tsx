import { useMemo, useState } from "react";
import { run, targets } from "../commands";
import { useApp } from "../store";
import type { PresetInfo } from "../types";

export default function PresetPanel() {
  const s = useApp((st) => st.state);
  const focusCh = useApp((st) => st.focusCh);
  const lastPreset = useApp((st) => st.lastPreset);
  const setLastPreset = useApp((st) => st.setLastPreset);

  const presets = s?.presets ?? [];
  const cats: string[] = [];
  for (const p of presets) if (!cats.includes(p.category)) cats.push(p.category);
  const [activeCat, setActiveCat] = useState<string>("");
  // 默认选中第一个分类（未点选时回落到 cats[0]）
  const active = cats.includes(activeCat) ? activeCat : cats[0] ?? "";
  const shown = presets.filter((p) => p.category === active);

  const pick = async (p: PresetInfo) => {
    setLastPreset(focusCh, p.name);
    await run("pulse_hold", { pattern: p.name }, targets(focusCh));
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col rounded-[14px] border border-line bg-panel p-3">
      <h3 className="mb-2 flex-none text-[12px] font-semibold tracking-[1.5px] text-muted">自选组合</h3>
      <div className="mb-2 flex flex-none flex-wrap gap-1">
        {cats.map((c) => (
          <button
            key={c}
            onClick={() => setActiveCat(c)}
            className={`rounded-lg px-3 py-1 text-[12px] transition-colors ${
              active === c ? "bg-accent font-semibold text-ink" : "text-muted hover:bg-ink3 hover:text-text"
            }`}
          >
            {c}
          </button>
        ))}
      </div>
      <div className="flex min-h-0 flex-1 flex-col gap-1 overflow-y-auto pr-1">
        {shown.map((p) => (
          <PresetCard key={p.name} preset={p} active={lastPreset[focusCh] === p.name} onPick={() => pick(p)} />
        ))}
        {!shown.length && (
          <p className="text-[11px] text-faint">该分类暂无波形（可在 config\waveforms.yaml 自定义）</p>
        )}
      </div>
    </div>
  );
}

/**
 * 帧 → 分段列表：每段 {n: 帧数, amp: 段内峰值 0~1}，
 * 与实时波形卡同一套解析逻辑（宽度∝时长，高度∝强度）。
 * 帧格式：每帧 8 字节十六进制，前 4 字节 A 通道振幅(00~64)。
 */
function useSegments(frames: string[]): { n: number; amp: number }[] | null {
  return useMemo(() => {
    if (!frames?.length) return null;
    const out: { n: number; amp: number }[] = [];
    let cur: { n: number; peak: number } | null = null;
    let gap = 0;
    for (const f of frames) {
      const a = parseInt(f.slice(0, 2), 16) / 100;
      if (a > 0.05) {
        if (!cur) {
          if (gap > 0) out.push({ n: gap, amp: 0 });
          gap = 0;
          cur = { n: 1, peak: a };
        } else {
          cur.n += 1;
          cur.peak = Math.max(cur.peak, a);
        }
      } else {
        gap += 1;
        if (cur) {
          out.push({ n: cur.n, amp: cur.peak });
          cur = null;
        }
      }
    }
    if (cur) out.push({ n: cur.n, amp: cur.peak });
    return out;
  }, [frames]);
}

function PresetCard({ preset, active, onPick }: { preset: PresetInfo; active: boolean; onPick: () => void }) {
  const items = useSegments(preset.frames ?? []);
  return (
    <div
      onClick={onPick}
      className={`flex cursor-pointer items-center gap-2.5 rounded-[10px] border px-2.5 py-1.5 transition-colors ${
        active ? "border-accent bg-accent" : "border-line bg-panel2 hover:border-line2"
      }`}
    >
      <div
        className={`w-[62px] flex-none truncate font-semibold leading-tight text-[13px] ${
          active ? "text-ink" : "text-text"
        }`}
        title={preset.name}
      >
        {preset.name}
      </div>
      {items ? (
        <div className="flex h-[18px] min-w-0 flex-1 items-end gap-[1px] overflow-hidden">
          {items.map((it, i) =>
            it.amp > 0 ? (
              <div
                key={i}
                style={{
                  flexGrow: it.n,
                  flexBasis: 0,
                  height: `${Math.max(10, Math.round(it.amp * 100))}%`,
                  background: "linear-gradient(to top, #f7d97a, #ffe59a)",
                  borderRadius: 1,
                  boxShadow: "0 0 3px rgba(247,217,122,0.35)",
                }}
              />
            ) : (
              <div key={i} style={{ flexGrow: it.n, flexBasis: 0 }} />
            )
          )}
        </div>
      ) : (
        <div className="flex-1" />
      )}
    </div>
  );
}
