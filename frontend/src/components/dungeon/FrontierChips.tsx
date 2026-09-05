/**
 * 深渊路网 · 主栏岔口卡（D26 §3.1 双入口）。awaiting_move 时替代 Choices 出现在选项区。
 * 复用 Choices 的按钮语法：左编号、图标 + 房型；gated 显示锁与原因（unmetText）；
 * inlineConfirm=true 时（mid/窄屏看不到地图确认条）在卡下方给一份 [前往][取消]。
 */
import { Lock } from "lucide-react";
import { useT } from "../../i18n";
import RoomIcon from "./RoomIcon";
import { gateText, roomLabel } from "./labels";
import type { RouteActions } from "./useRouteActions";

export default function FrontierChips({ acts, inlineConfirm = false }: { acts: RouteActions; inlineConfirm?: boolean }) {
  const t = useT();
  const { map, awaiting, blocked, estop, selectedNodeId, select, confirm, cancel } = acts;
  if (!map || !awaiting) return null;
  const opts = map.nodes.filter((n) => n.state === "reachable" || n.state === "gated").sort((a, b) => a.col - b.col);
  const selected = selectedNodeId ? opts.find((n) => n.id === selectedNodeId) : undefined;

  return (
    <div>
      <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-faint">{t("选择下一处")}</p>
      {estop && <p className="mb-2 text-[11px] font-semibold text-bad">{t("急停中，路网已锁")}</p>}
      <div className="flex flex-col gap-2">
        {opts.length === 0 && <p className="text-xs text-faint">{t("无可达岔口")}</p>}
        {opts.map((n, i) => {
          const on = selectedNodeId === n.id;
          const gated = n.state === "gated";
          const why = gated ? gateText(n.gate, t) : "";
          return (
            <button
              key={n.id}
              type="button"
              disabled={blocked}
              aria-pressed={on || undefined}
              onClick={() => select(n.id)}
              className={`dg-rise flex items-center gap-3 rounded-[12px] border px-4 py-2.5 text-left transition-colors disabled:cursor-not-allowed disabled:opacity-60 ${
                on
                  ? "border-accent2 bg-accent2/15"
                  : gated
                    ? "border-line/50 bg-ink3/40"
                    : "border-accent2/50 bg-ink3 hover:border-accent hover:bg-panel"
              }`}
              style={{ animationDelay: `${i * 50}ms` }}
            >
              <span className={`w-4 flex-none text-[11px] ${gated ? "text-faint" : "text-accent"}`}>{i + 1}</span>
              <RoomIcon room={n.revealed ? n.room : "unknown"} size={16} />
              <span className="min-w-0 flex-1">
                <span className={`block text-[14px] leading-snug ${on ? "text-accent2" : gated ? "text-faint" : "text-text"}`}>
                  {t(roomLabel(n.room))}
                  {n.title ? `「${n.title}」` : ""}
                </span>
                {gated && (
                  <span className="mt-0.5 block text-[11px] text-bad/80">
                    <Lock size={10} className="mr-1 inline" />
                    {why || t("被门槛拦住")}
                  </span>
                )}
              </span>
            </button>
          );
        })}
      </div>
      {inlineConfirm && selected && !blocked && (
        <div className="mt-3 flex gap-2">
          <button type="button" onClick={confirm} className="h-11 flex-1 rounded-lg bg-accent2 text-sm font-bold text-ink">
            {t("前往 · {what}", { what: t(roomLabel(selected.room)) })}
          </button>
          <button type="button" onClick={cancel} className="h-11 rounded-lg border border-line px-3 text-sm text-muted hover:border-line2">
            {t("取消")}
          </button>
        </div>
      )}
    </div>
  );
}
