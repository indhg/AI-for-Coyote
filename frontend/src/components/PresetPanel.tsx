import { useState } from "react";
import { run, targets } from "../commands";
import { useApp, useLayout } from "../store";
import { useT } from "../i18n";
import type { PresetInfo } from "../types";

export default function PresetPanel() {
  const t = useT();
  const s = useApp((st) => st.state);
  const focusCh = useApp((st) => st.focusCh);
  const lastPreset = useApp((st) => st.lastPreset);
  const setLastPreset = useApp((st) => st.setLastPreset);
  const controlW = useLayout((st) => st.controlW);

  const presets = s?.presets ?? [];
  const estop = !!s?.estop;
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
      <h3 className="mb-2 flex-none text-[12px] font-semibold tracking-[1.5px] text-muted">{t("自选组合")}</h3>
      {estop && (
        <p className="mb-2 flex-none rounded-lg border border-red-500/60 bg-red-950/40 px-2 py-1.5 text-[11px] leading-relaxed text-red-300">
          {t("急停中：所有设备动作被拒绝。点「解除急停」恢复（焦点不在输入框时长按空格 1 秒触发急停）。")}
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
            {t(c)}
          </button>
        ))}
      </div>
      <div
        className={`grid min-h-0 flex-1 content-start gap-1 overflow-y-auto pr-1 ${
          controlW < 400 ? "grid-cols-3" : "grid-cols-6"
        }`}
      >
        {shown.map((p) => (
          <PresetCard key={p.name} preset={p} active={lastPreset[focusCh] === p.name} onPick={() => pick(p)} />
        ))}
        {!shown.length && (
          <p className="col-span-full text-[11px] text-faint">{t("该分类暂无波形（可在 config\\waveforms.yaml 自定义）")}</p>
        )}
      </div>
    </div>
  );
}

function PresetCard({ preset, active, onPick }: { preset: PresetInfo; active: boolean; onPick: () => void }) {
  const t = useT();
  return (
    <div
      onClick={onPick}
      className={`flex aspect-square cursor-pointer flex-col items-center justify-center rounded-[8px] border px-0.5 text-center transition-colors ${
        active ? "border-accent bg-accent" : "border-line bg-panel2 hover:border-line2"
      }`}
    >
      <div
        className={`line-clamp-2 w-full break-all text-[13px] font-semibold leading-tight ${
          active ? "text-ink" : "text-text"
        }`}
        title={t(preset.name)}
      >
        {t(preset.name)}
      </div>
    </div>
  );
}
