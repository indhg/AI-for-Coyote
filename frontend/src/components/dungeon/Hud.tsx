/**
 * HUD：身体（HP/MP）· 三轴（淫化 / 恶堕 / 魔化）· 三维（力/巧/智）· 淫纹阶段 · 骰子。
 * 全部来自 run.snapshot() 拍平字段。窄屏折叠成一行摘要，点开展开。
 * 不含任何设备强度 / 通道 / 波形信息。
 */
import { useState } from "react";
import { ChevronDown, ChevronUp, Dices, Skull } from "lucide-react";
import { useT } from "../../i18n";
import type { DungeonRun } from "../../types";
import { MA_TICKS, MARK_ORDER, attrCode, attrLabel, maTierDesc, maTierLabel, markIndex, markLabel } from "./labels";

export default function Hud({ run }: { run: DungeonRun }) {
  const t = useT();
  const [open, setOpen] = useState(false);
  const mi = markIndex(run.mark_stage);
  return (
    <div className="flex-none border-b border-line bg-ink2/80 px-4 py-2 text-[12px]">
      {/* 摘要行：任何宽度都显示 */}
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <Pips label="HP" value={run.hp} max={10} tone="vital" />
        <Pips label="MP" value={run.mp} max={10} tone="ok" />
        <span className="text-muted">
          {t("淫纹")} <b className="text-accent">{t(markLabel(run.mark_stage))}</b>
        </span>
        <span className="text-muted" title={t(maTierDesc(run.ma_tier))}>
          {t("魔化")} <b className="text-demon">{t(maTierLabel(run.ma_tier))}</b>
        </span>
        {run.crossed_gate && <span className="rounded border border-bad/60 px-1.5 text-[11px] text-bad">{t("已跨过沉没之门")}</span>}
        {run.defeats > 0 && (
          <span className="flex items-center gap-1 text-faint">
            <Skull size={11} /> {t("败北 {n}", { n: run.defeats })}
          </span>
        )}
        <button
          onClick={() => setOpen((o) => !o)}
          className="ml-auto flex items-center gap-1 text-[11px] text-faint hover:text-text @lg:hidden"
        >
          {open ? t("收起") : t("详情")} {open ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
        </button>
      </div>
      {/* 详情：宽面板常显，窄屏按需展开 */}
      <div className={`${open ? "block" : "hidden"} @lg:block`}>
        <div className="mt-2 grid gap-x-4 gap-y-1.5 @md:grid-cols-3">
          <Axis label={t("淫化")} value={run.yin_hua} max={100} ticks={[25, 50, 75]} color="bg-lust" />
          <Axis label={t("恶堕")} value={run.e_duo} max={100} ticks={[25, 50, 75]} color="bg-arcane" />
          <Axis label={t("魔化")} value={run.ma} max={Math.max(500, run.ma)} ticks={MA_TICKS} color="bg-demon" sub={t(maTierDesc(run.ma_tier))} />
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1">
          <span className="flex items-center gap-2">
            {(["str", "dex", "int"] as const).map((a) => (
              <span key={a} className="rounded-md border border-line bg-ink3 px-2 py-0.5" title={attrCode(a)}>
                <span className="text-faint">{t(attrLabel(a))}</span> <b className="text-text">{run[a]}</b>
              </span>
            ))}
          </span>
          <span className="flex items-center gap-1.5" title={t("淫纹阶段：无 → 萌芽 → 显现 → 成形 → 定型")}>
            <span className="text-faint">{t("淫纹")}</span>
            {MARK_ORDER.map((s, i) => (
              <span
                key={s}
                className={`h-2 w-2 rounded-full ${i <= mi && mi > 0 ? "bg-accent shadow-[0_0_6px_var(--color-accent)]" : "bg-ink3 ring-1 ring-line"}`}
                title={t(markLabel(s))}
              />
            ))}
          </span>
          <span className="flex items-center gap-1 text-muted" title={run.dice_desc}>
            <Dices size={12} className="text-accent" /> {run.dice_name}
            <span className="text-faint">· {run.dice_desc}</span>
          </span>
        </div>
      </div>
    </div>
  );
}

function Pips({ label, value, max, tone }: { label: string; value: number; max: number; tone: "vital" | "ok" }) {
  const v = Math.max(0, Math.min(max, value));
  const on = tone === "vital" ? "bg-vital" : "bg-ok";
  return (
    <span className="flex items-center gap-1.5" title={`${label} ${v}/${max}`}>
      <span className="text-faint">{label}</span>
      <span className="flex gap-[2px]">
        {Array.from({ length: max }, (_, i) => (
          <span key={i} className={`h-2.5 w-1.5 rounded-[2px] ${i < v ? on : "bg-ink3 ring-1 ring-line"}`} />
        ))}
      </span>
      <b className={v <= 2 ? "text-bad" : "text-text"}>{v}</b>
    </span>
  );
}

function Axis({ label, value, max, ticks, color, sub }: { label: string; value: number; max: number; ticks: number[]; color: string; sub?: string }) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  return (
    <div>
      <div className="flex items-baseline justify-between">
        <span className="text-faint">{label}</span>
        <span className="text-text">
          <b>{value}</b>
          {sub && <span className="ml-1 text-[10px] text-faint">{sub}</span>}
        </span>
      </div>
      <div className="relative mt-1 h-1.5 w-full rounded-full bg-ink3">
        <div className={`h-full rounded-full ${color} transition-[width] duration-500`} style={{ width: `${pct}%` }} />
        {ticks.map((tk) => (
          <span key={tk} className="absolute top-[-2px] h-[10px] w-px bg-line" style={{ left: `${(tk / max) * 100}%` }} />
        ))}
      </div>
    </div>
  );
}
