/**
 * 结算回显：上一步选了什么 → 掷点（属性 + 骰 = 总和 vs 目标）→ 折叠 / 数值变化 / 骰子获得 / 败北 / 沉没之门。
 * 结局本身由 EndingCard 负责，这里只处理过程。
 */
import { Dices, Skull } from "lucide-react";
import { useT } from "../../i18n";
import type { DungeonOutcome } from "../../types";
import { attrLabel, diceName, effectLabel, markLabel } from "./labels";

export default function OutcomeCard({ outcome }: { outcome: DungeonOutcome }) {
  const t = useT();
  const ck = outcome.check;
  const fx = outcome.effects.filter((a) => !(typeof a.value === "number" && a.value === 0));
  return (
    <div className="dg-rise rounded-[12px] border border-line bg-panel2/70 p-3 text-[12px]">
      <p className="text-muted">
        {t("你选了")} <span className="text-text">「{outcome.label}」</span>
      </p>
      {ck && (
        <div className={`mt-2 flex flex-wrap items-center gap-2 rounded-lg border px-2.5 py-1.5 ${ck.success ? "border-ok/50 bg-ok/10" : "border-bad/50 bg-bad/10"}`}>
          <Dices size={14} className={ck.success ? "text-ok" : "text-bad"} />
          <span className="text-text">
            {t(attrLabel(ck.attr))} {ck.attr_value}
            {" + "}
            {t(diceName(ck.dice))} <b>{ck.zeroed ? 0 : ck.bonus}</b>
            {ck.zeroed && <span className="ml-1 text-bad">{t("（归零！）")}</span>}
            {" = "}
            <b className={ck.success ? "text-ok" : "text-bad"}>{ck.total}</b>
            <span className="text-muted">
              {" "}
              {ck.success ? "≥" : "<"} {ck.tn}
            </span>
          </span>
          <span className={`ml-auto font-bold ${ck.success ? "text-ok" : "text-bad"}`}>{ck.success ? t("成功") : t("失败")}</span>
          {outcome.folded && (
            <span className="w-full text-[11px] text-bad/80">
              {outcome.effective_label && outcome.effective_choice !== outcome.choice
                ? t("行动折叠为「{label}」", { label: outcome.effective_label })
                : t("行动落空，走了另一条路")}
            </span>
          )}
        </div>
      )}
      {(fx.length > 0 || outcome.dice_gain) && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {fx.map((a, i) => (
            <EffectChip key={i} k={a.key} value={a.value} before={a.before} after={a.after} />
          ))}
          {outcome.dice_gain && (
            <span className="rounded border border-accent/50 bg-accent/10 px-1.5 py-0.5 text-accent">
              <Dices size={11} className="mr-1 inline" />
              {t("获得 {d}", { d: t(diceName(outcome.dice_gain)) })}
            </span>
          )}
        </div>
      )}
      {outcome.defeat && (
        <p className="mt-2 flex items-center gap-1.5 font-semibold text-bad">
          <Skull size={13} /> {t("败北 · 被拖回祭坛")}
        </p>
      )}
      {outcome.gate_checked && (
        <p className={`mt-2 font-semibold ${outcome.crossed ? "text-demon" : "text-muted"}`}>
          {outcome.crossed ? t("你跨过了沉没之门") : t("沉没之门没有开：淫纹或魔化还不够深")}
        </p>
      )}
    </div>
  );
}

function EffectChip({ k, value, before, after }: { k: string; value: number | boolean | string; before: number | string; after: number | string }) {
  const t = useT();
  if (k.startsWith("stage")) {
    return (
      <span className="rounded border border-accent/40 px-1.5 py-0.5 text-accent">
        {t(effectLabel(k))} {t(markLabel(String(before)))} → {t(markLabel(String(after)))}
      </span>
    );
  }
  const num = typeof value === "number" ? value : 0;
  const bad = k === "hp" || k === "mp" ? num < 0 : k === "yin_hua" || k === "e_duo" || k === "ma" ? num > 0 : num < 0;
  return (
    <span className={`rounded border px-1.5 py-0.5 ${bad ? "border-bad/40 text-bad" : "border-ok/40 text-ok"}`}>
      {t(effectLabel(k))} {num > 0 ? `+${num}` : num} <span className="opacity-70">→ {after}</span>
    </span>
  );
}
