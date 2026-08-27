import { useState } from "react";
import { run, targets } from "../commands";
import { useApp } from "../store";
import type { PresetInfo } from "../types";

export default function PresetPanel() {
  const s = useApp((st) => st.state);
  const focusCh = useApp((st) => st.focusCh);
  const lastPreset = useApp((st) => st.lastPreset);
  const setLastPreset = useApp((st) => st.setLastPreset);

  const presets = s?.presets ?? [];
  const paired = s?.relay_status === "paired";
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
      {!paired && (
        <p className="mb-2 flex-none rounded-lg border border-line bg-ink3 px-2 py-1.5 text-[11px] leading-relaxed text-muted">
          郊狼未配对：强度/波形暂不生效。用 DG-LAB App 扫右侧二维码重新配对。
        </p>
      )}
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

function PresetCard({ preset, active, onPick }: { preset: PresetInfo; active: boolean; onPick: () => void }) {
  return (
    <div
      onClick={onPick}
      className={`flex cursor-pointer items-center gap-2.5 rounded-[10px] border px-3 py-1.5 transition-colors ${
        active ? "border-accent bg-accent" : "border-line bg-panel2 hover:border-line2"
      }`}
    >
      <div
        className={`flex-1 truncate font-semibold leading-tight text-[13px] ${
          active ? "text-ink" : "text-text"
        }`}
        title={preset.name}
      >
        {preset.name}
      </div>
    </div>
  );
}
