/**
 * 深渊路网 · Boss 下方三扇结局门（D26 §1.3，裁决：只读高亮）。
 * 结局由 Boss 事件卡的 choice 决定；这里只读 terminus.endings[].reached 与 run.ending，名字走 theme_labels.endings。
 */
import { useT } from "../../i18n";
import type { DungeonRouteEnding } from "../../types";
import { endingLabel } from "./labels";

const KINDS = ["escape", "stay", "sink"] as const;

export default function RouteTerminus({
  endings,
  phase,
  ending,
}: {
  endings: DungeonRouteEnding[];
  phase: string;
  ending: string | null;
}) {
  const t = useT();
  const reached = ending ?? endings.find((e) => e.reached)?.kind ?? null;
  const over = phase === "ended" || phase === "locked";
  return (
    <div className="relative flex items-end justify-center gap-4 px-2 pb-1 pt-1" style={{ height: 56 }} role="group" aria-label={t("结局门")}>
      {KINDS.map((kind) => {
        const on = reached === kind;
        const dim = over && reached && reached !== kind;
        const fill =
          on && kind === "escape"
            ? "border-accent bg-accent/30 text-accent"
            : on && kind === "stay"
              ? "border-warn bg-warn/25 text-warn"
              : on && kind === "sink"
                ? "border-demon bg-demon/25 text-demon"
                : "border-line/40 text-faint";
        const name = t(endingLabel(kind));
        return (
          <span
            key={kind}
            className={`flex h-7 w-5 flex-col items-center justify-end rounded-sm border-2 ${fill}${dim ? " border-dashed opacity-40" : ""}`}
            title={name}
            aria-label={`${name}${on ? " · " + t("已到达") : ""}`}
          >
            {on && <span className="mb-0.5 whitespace-nowrap text-[9px] leading-none">{name.slice(0, 2)}</span>}
          </span>
        );
      })}
      {over && reached && (
        <span className="absolute bottom-1 right-3 text-[10px] text-muted">
          {t(endingLabel(reached))}
          {reached === "sink" ? ` · ${t("已沉")}` : ""}
        </span>
      )}
    </div>
  );
}
