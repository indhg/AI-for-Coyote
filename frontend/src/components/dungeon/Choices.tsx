/**
 * 选项列表：disabled/disabled_reason 灰显；check{attr,tn,attr_value,dice} 显示为「巧 7 · 目标 8 · D4」+ 可行性色；
 * 出口类结算（安全区/离开/结局）外露小标签帮玩家找路；estop_overrides 显示「戏内无法拒绝」。
 * 急停 / 忙碌 / 结局态 → 全部禁用。
 */
import { Dices, Lock } from "lucide-react";
import { useT } from "../../i18n";
import type { DungeonChoice } from "../../types";
import { SETTLEMENT_SHOWN, attrLabel, diceName, feasibility, settlementLabel, unmetText } from "./labels";

export default function Choices({ choices, blocked, onPick }: { choices: DungeonChoice[]; blocked: boolean; onPick: (id: string) => void }) {
  const t = useT();
  if (!choices.length) return null;
  return (
    <div className="flex flex-col gap-2">
      {choices.map((c, i) => {
        const dis = blocked || c.disabled;
        const fz = c.check ? feasibility(c.check.attr_value, c.check.tn, c.check.dice) : null;
        return (
          <button
            key={c.id}
            disabled={dis}
            onClick={() => onPick(c.id)}
            aria-disabled={dis}
            className={`dg-rise group rounded-[12px] border px-4 py-2.5 text-left transition-colors ${
              c.disabled
                ? "cursor-not-allowed border-line/50 bg-ink3/40 text-faint"
                : blocked
                  ? "cursor-not-allowed border-line/60 bg-ink3 text-muted opacity-60"
                  : "border-accent2/50 bg-ink3 text-text hover:border-accent hover:bg-panel"
            }`}
            style={{ animationDelay: `${i * 50}ms` }}
          >
            <div className="flex items-start gap-3">
              <span className={`mt-0.5 flex-none text-[11px] ${c.disabled ? "text-faint" : "text-accent"}`}>{c.id}</span>
              <span className="min-w-0 flex-1">
                <span className="text-[14px] leading-snug">{c.label}</span>
                <span className="mt-1 flex flex-wrap items-center gap-1.5 text-[11px]">
                  {c.check && (
                    <span
                      className={`flex items-center gap-1 rounded border px-1.5 py-0.5 ${
                        c.disabled
                          ? "border-line/50 text-faint"
                          : fz === "sure"
                            ? "border-ok/50 text-ok"
                            : fz === "dice"
                              ? "border-warn/50 text-warn"
                              : "border-bad/50 text-bad"
                      }`}
                      title={
                        t("检定：{attr} {v} + 骰子加成 ≥ {tn} 即成功", { attr: t(attrLabel(c.check.attr)), v: c.check.attr_value, tn: c.check.tn }) +
                        (c.check.dice === "ed6" ? "\n" + t("永恒 D6：15% 概率归零") : "")
                      }
                    >
                      <Dices size={11} />
                      {t(attrLabel(c.check.attr))} {c.check.attr_value} · {t("目标 {tn}", { tn: c.check.tn })} · {t(diceName(c.check.dice))}
                      <span className="opacity-80">{fz === "sure" ? t("稳过") : fz === "dice" ? t("靠骰") : t("够不到")}</span>
                    </span>
                  )}
                  {SETTLEMENT_SHOWN.has(c.settlement) && (
                    <span className="rounded border border-arcane/40 px-1.5 py-0.5 text-arcane">{t(settlementLabel(c.settlement))}</span>
                  )}
                  {c.estop_overrides && (
                    <span className="flex items-center gap-1 rounded border border-line px-1.5 py-0.5 text-faint" title={t("剧情里无法拒绝；急停仍然有效")}>
                      <Lock size={10} /> {t("戏内无法拒绝")}
                    </span>
                  )}
                </span>
                {c.disabled && (c.unmet?.length || c.disabled_reason) && (
                  <span className="mt-1 block text-[11px] text-bad/80">
                    <Lock size={10} className="mr-1 inline" />
                    {c.unmet?.length ? c.unmet.map((u) => unmetText(u, t)).join("；") : c.disabled_reason}
                  </span>
                )}
              </span>
            </div>
          </button>
        );
      })}
    </div>
  );
}
