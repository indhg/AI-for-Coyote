/**
 * 结局态（phase=ended|locked）：正文（结局 exit 句已由后端塞进 narrative）之外，
 * 给一张结算卡：结局名 / 回合与败北 / 淫纹与魔化 / 体感已清理 提示 / 再开一局 · 回大厅。
 * locked（沉）= 不再给探索选项，卡面更暗。
 */
import { Flag, Home, RotateCcw } from "lucide-react";
import { useT } from "../../i18n";
import type { DungeonRun } from "../../types";
import { endingLabel, maTierLabel, markLabel } from "./labels";

export default function EndingCard({ run, busy, onAgain, onRestart }: { run: DungeonRun; busy: boolean; onAgain: () => void; onRestart: () => void }) {
  const t = useT();
  const locked = run.phase === "locked";
  return (
    <div className={`dg-rise rounded-[14px] border p-4 ${locked ? "border-demon/60 bg-[#1a1226]" : "border-accent/60 bg-accent/10"}`}>
      <p className={`flex items-center gap-2 text-[11px] uppercase tracking-wide ${locked ? "text-demon" : "text-accent"}`}>
        <Flag size={12} /> {locked ? t("本局已沉没并锁定") : t("本局已结束")}
      </p>
      <h3 className={`mt-1 text-xl font-bold ${locked ? "text-demon" : "text-accent"}`}>{t(endingLabel(run.ending))}</h3>
      <div className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1 text-[12px] text-muted @md:grid-cols-4">
        <span>
          {t("回合")} <b className="text-text">{run.turn}</b>
        </span>
        <span>
          {t("败北")} <b className="text-text">{run.defeats}</b>
        </span>
        <span>
          {t("淫纹")} <b className="text-text">{t(markLabel(run.mark_stage))}</b>
        </span>
        <span>
          {t("魔化")} <b className="text-text">{t(maTierLabel(run.ma_tier))}</b>
        </span>
      </div>
      <p className="mt-3 text-[11px] text-faint">
        {t("体感已清理")}
        {locked && <span> · {t("这一局不再给探索选项")}</span>}
      </p>
      <div className="mt-4 flex flex-wrap gap-2">
        <button onClick={onAgain} disabled={busy} className="flex items-center gap-1.5 rounded-[10px] bg-accent2 px-4 py-2 text-sm font-bold text-ink disabled:opacity-40">
          <RotateCcw size={14} /> {t("再开一局")}
        </button>
        <button
          onClick={onRestart}
          disabled={busy}
          className="flex items-center gap-1.5 rounded-[10px] border border-line px-4 py-2 text-sm text-muted hover:border-line2 hover:text-text disabled:opacity-40"
        >
          <Home size={14} /> {t("回大厅")}
        </button>
      </div>
    </div>
  );
}
