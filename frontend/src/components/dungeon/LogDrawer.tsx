/**
 * 检定记录抽屉：run.log（后端保留尾 20 条）逐条可读化。advance 条目含 check 时高亮掷点。
 * 可切换「只看检定」。
 */
import { useState } from "react";
import { ChevronDown, ChevronUp, Dices, ScrollText } from "lucide-react";
import { useT } from "../../i18n";
import type { DungeonLogEntry, DungeonMapNode } from "../../types";
import { attrLabel, diceName, effectLabel, endingLabel, markLabel } from "./labels";

export default function LogDrawer({ log, nodes }: { log: DungeonLogEntry[]; nodes: Array<Pick<DungeonMapNode, "id"> & { title?: string }> }) {
  const t = useT();
  const [open, setOpen] = useState(false);
  const [onlyChecks, setOnlyChecks] = useState(false);
  const title = (eid?: string) => nodes.find((n) => n.id === eid)?.title ?? eid ?? "";
  const checks = log.filter((e) => e.type === "advance" && e.check).length;
  const rows = [...log].reverse().filter((e) => !onlyChecks || (e.type === "advance" && e.check));
  return (
    <div className="border-t border-line">
      <div className="flex items-center gap-3 px-4 py-2 text-[11px]">
        <button onClick={() => setOpen((o) => !o)} className="flex items-center gap-1 text-muted hover:text-text">
          <ScrollText size={12} /> {t("检定记录")} <span className="text-faint">({checks})</span>
          {open ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
        </button>
        {open && (
          <label className="flex items-center gap-1 text-faint">
            <input type="checkbox" checked={onlyChecks} onChange={(e) => setOnlyChecks(e.target.checked)} /> {t("只看检定")}
          </label>
        )}
      </div>
      {open && (
        <ol className="max-h-56 overflow-y-auto px-4 pb-3 text-[11px] leading-relaxed">
          {rows.length === 0 && <li className="text-faint">{t("还没有记录")}</li>}
          {rows.map((e, i) => (
            <li key={`${e.turn}-${i}`} className="border-t border-line/40 py-1 first:border-t-0">
              <span className="mr-2 text-faint">T{e.turn}</span>
              <Row e={e} title={title} />
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

function Row({ e, title }: { e: DungeonLogEntry; title: (eid?: string) => string }) {
  const t = useT();
  if (e.type === "start") {
    return (
      <span className="text-muted">
        {t("开局")} · {t("力量")} {e.str} / {t("敏捷")} {e.dex} / {t("智慧")} {e.int}
      </span>
    );
  }
  if (e.type === "enter") {
    return (
      <span className="text-muted">
        {t("进入")} <span className="text-text">{title(e.event)}</span>
        {(e.visit_n ?? 1) > 1 && <span className="text-faint"> · {t("第 {n} 次", { n: e.visit_n ?? 1 })}</span>}
      </span>
    );
  }
  if (e.type === "advance") {
    const ck = e.check;
    return (
      <span className="text-muted">
        <span className="text-text">{title(e.event)}</span> · {t("选 {n}", { n: e.choice ?? "?" })}「{e.label}」
        {ck && (
          <span className={`ml-1 inline-flex items-center gap-1 rounded border px-1 ${ck.success ? "border-ok/50 text-ok" : "border-bad/50 text-bad"}`}>
            <Dices size={10} /> {t(attrLabel(ck.attr))} {ck.attr_value}+{t(diceName(ck.dice))}
            {ck.zeroed ? "0" : ck.bonus}={ck.total} {ck.success ? "≥" : "<"} {ck.tn}
          </span>
        )}
        {e.folded_to != null && (
          <span className="ml-1 text-bad/80">{e.folded_label ? t("折叠为「{label}」", { label: e.folded_label }) : t("折叠→{n}", { n: e.folded_to })}</span>
        )}
        {(e.effects ?? [])
          .filter((a) => !(typeof a.value === "number" && a.value === 0))
          .map((a, i) => (
            <span key={i} className="ml-1 text-faint">
              {t(effectLabel(a.key))}
              {a.key.startsWith("stage") ? ` ${t(markLabel(String(a.after)))}` : ` ${typeof a.value === "number" && a.value > 0 ? "+" : ""}${a.value}`}
            </span>
          ))}
        {e.dice_gain && <span className="ml-1 text-accent">{t("获得 {d}", { d: t(diceName(e.dice_gain)) })}</span>}
        {e.defeat && <span className="ml-1 font-semibold text-bad">{t("败北")}</span>}
        {e.gate_check && <span className={`ml-1 ${e.gate_check.crossed ? "text-demon" : "text-faint"}`}>{e.gate_check.crossed ? t("跨门") : t("门未开")}</span>}
        {e.ending && <span className="ml-1 font-semibold text-accent">{t(endingLabel(e.ending))}</span>}
      </span>
    );
  }
  return <span className="text-faint">{e.type}</span>;
}
