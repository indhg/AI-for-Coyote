/**
 * 进行中视图。布局（Tailwind 容器查询，按面板自身宽度切换）：
 *   宽（@lg ≥ 32rem）：[工具条] / [HUD 横条] / [正文+选项（D24：地图已移右栏，正文占满）] / [检定记录]
 *   窄：              [工具条] / [HUD 摘要行(可展开)] / [深度计(chain 可展开剖面 / map 展开路网抽屉)] / [正文+选项] / [检定记录]
 * D30：render.map.mode==="map" 且 awaiting_move 时，选项区 Choices → 岔口卡 FrontierChips；选路走 useRouteActions。
 */
import { FolderOpen, Home, Map as MapIcon, Save } from "lucide-react";
import { useT } from "../../i18n";
import { useApp, useDungeon, useLayout } from "../../store";
import { isRouteMap, type DungeonRender } from "../../types";
import type { PanelError } from "../DungeonPanel";
import AbyssMap from "./AbyssMap";
import Choices from "./Choices";
import EndingCard from "./EndingCard";
import ErrorBox from "./ErrorBox";
import FrontierChips from "./FrontierChips";
import Hud from "./Hud";
import LogDrawer from "./LogDrawer";
import OutcomeCard from "./OutcomeCard";
import RoomIcon from "./RoomIcon";
import RouteMap from "./RouteMap";
import RouteSheet from "./RouteSheet";
import { BAND_ORDER, bandLabel, bandShort, bandTier, roomLabel } from "./labels";
import { useRouteActions } from "./useRouteActions";

interface Props {
  render: DungeonRender;
  busy: boolean;
  estop: boolean;
  error: PanelError | null;
  notice: string | null;
  onAdvance: (id: string) => void;
  onSave: () => void;
  onLoad: () => void;
  onRestart: () => void;
  onAgain: () => void;
  onClearError: () => void;
}

export default function RunView({ render, busy, estop, error, notice, onAdvance, onSave, onLoad, onRestart, onAgain, onClearError }: Props) {
  const t = useT();
  const { run, event: ev, narrative, feedback, map, outcome } = render;
  const ended = run.phase === "ended" || run.phase === "locked";
  const blocked = busy || estop || ended;
  const dropped = render.dropped.length;
  const packTitle = usePackTitle(ev.theme_id);
  // D24：宽屏下地图常驻右栏，面板内不再画右侧地图列（mid/窄屏保持面板内折叠/抽屉）
  const wide = useLayout((s) => s.mode) === "wide";
  const acts = useRouteActions();
  const route = isRouteMap(map) ? map : null;
  const awaiting = !!route && route.awaiting_move && !ended;
  const sheetOpen = useDungeon((s) => s.routeSheetOpen);
  const setSheetOpen = useDungeon((s) => s.setRouteSheetOpen);
  const curNode = route ? route.nodes.find((n) => n.id === route.current) : undefined;
  // move 帧的 outcome（settlement="move"）不是选项结算，不回显
  const showOutcome = !!outcome && !outcome.ending && outcome.settlement !== "move";

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      {/* 工具条 */}
      <div className="flex flex-none flex-wrap items-center gap-x-3 gap-y-1 border-b border-line px-4 py-2 text-[11px] text-muted">
        <span className="font-semibold text-arcane">{packTitle}</span>
        <span className="flex items-center gap-1">
          <span className="text-accent">{bandTier(ev.band)}</span> {t(bandLabel(ev.band))} · <RoomIcon room={ev.room} size={11} /> {t(roomLabel(ev.room))}
        </span>
        {route && curNode ? (
          <span>{t("第 {f} / {F} 层", { f: curNode.floor, F: route.floors - 1 })}</span>
        ) : (
          <span>{t("回合 {n}", { n: run.turn })}</span>
        )}
        {!route && ev.visit_n > 1 && <span className="text-faint">{t("第 {n} 次来", { n: ev.visit_n })}</span>}
        <span className="ml-auto flex items-center gap-1">
          {notice && <span className="mr-2 text-ok">{notice}</span>}
          <Tool icon={<Save size={12} />} label={t("存档")} onClick={onSave} disabled={busy || ended} />
          <Tool icon={<FolderOpen size={12} />} label={t("读档")} onClick={onLoad} disabled={busy} />
          <Tool icon={<Home size={12} />} label={t("回大厅")} onClick={onRestart} disabled={busy} />
        </span>
      </div>

      <Hud run={run} />

      {/* 主体：宽 = 正文占满（地图在右栏）；窄 = 深度计在上、正文在下 */}
      <div className="flex min-h-0 flex-1 flex-col @lg:flex-row">
        {!wide && map.mode === "chain" && (
          <div className="order-1 @lg:order-2 @lg:w-[17rem] @lg:flex-none @lg:overflow-y-auto">
            <AbyssMap map={map} collapsedDefault mode="panel" />
          </div>
        )}
        {!wide && route && (
          <button
            type="button"
            onClick={() => setSheetOpen(true)}
            className="dg-strata order-1 flex w-full flex-none items-center gap-2 border-b border-line px-3 py-2 text-left text-[11px] text-muted hover:text-text"
            aria-expanded={sheetOpen}
          >
            <span className="flex gap-[3px]">
              {BAND_ORDER.filter((b) => route.nodes.some((n) => n.band === b)).map((b) => (
                <span
                  key={b}
                  className={`h-3 w-2 rounded-[2px] ${
                    curNode?.band === b
                      ? "bg-accent shadow-[0_0_6px_var(--color-accent)]"
                      : route.nodes.some((n) => n.band === b && (n.state === "visited" || n.state === "current"))
                        ? "bg-arcane/70"
                        : "bg-ink3 ring-1 ring-line"
                  }`}
                />
              ))}
            </span>
            {curNode && (
              <span className="min-w-0 truncate">
                {t("第 {f} / {F} 层", { f: curNode.floor, F: route.floors - 1 })} · {t(bandShort(curNode.band))} · {t(roomLabel(curNode.room))}
                {curNode.title ? ` · ${curNode.title}` : ""}
              </span>
            )}
            <span className="ml-auto flex flex-none items-center gap-1 text-faint">
              <MapIcon size={12} /> {t("展开路网")}
            </span>
          </button>
        )}
        <div className="order-2 min-h-0 flex-1 overflow-y-auto px-4 py-3 @lg:order-1">
          {showOutcome && outcome && (
            <div className="mb-3">
              <OutcomeCard outcome={outcome} />
            </div>
          )}
          <article className={`rounded-[14px] border p-4 ${ended ? "border-line bg-panel/60" : "border-arcane/50 bg-panel"}`}>
            <h3 className="text-lg font-semibold text-text">{ev.title}</h3>
            <p className="mt-2 whitespace-pre-wrap text-[15px] leading-relaxed text-text">{narrative?.text ?? ""}</p>
            <p className="mt-3 flex flex-wrap items-center gap-x-3 text-[11px] text-arcane">
              <span>{t("体感[{hint}]", { hint: feedback.hint })}</span>
              {dropped > 0 && <span className="text-faint">{t("部分体感被安全层拦下")}</span>}
              {ev.variant.count > 1 && <span className="text-faint">{t("版本 {i}/{n}", { i: ev.variant.index + 1, n: ev.variant.count })}</span>}
            </p>
          </article>
          {error && (
            <div className="mt-3">
              <ErrorBox error={error} onClose={onClearError} onNew={onAgain} />
            </div>
          )}
          <div className="mt-3 pb-4">
            {ended ? (
              <EndingCard run={run} busy={busy} onAgain={onAgain} onRestart={onRestart} />
            ) : awaiting ? (
              <FrontierChips acts={acts} inlineConfirm={!wide} />
            ) : (
              <>
                {estop && <p className="mb-2 text-[11px] font-semibold text-bad">{t("急停中，选项已禁用")}</p>}
                <Choices choices={ev.choices} blocked={blocked} onPick={onAdvance} />
              </>
            )}
          </div>
        </div>
      </div>

      <div className="flex-none pb-14">
        <LogDrawer log={run.log} nodes={map.nodes} />
      </div>

      {!wide && route && (
        <RouteSheet open={sheetOpen} onClose={() => setSheetOpen(false)}>
          <RouteMap map={route} acts={acts} mode="panel" />
        </RouteSheet>
      )}
    </div>
  );
}

function Tool({ icon, label, onClick, disabled }: { icon: React.ReactNode; label: string; onClick: () => void; disabled?: boolean }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      title={label}
      className="flex items-center gap-1 rounded-md border border-line bg-panel2 px-2 py-0.5 text-[11px] text-muted hover:border-line2 hover:text-text disabled:opacity-40"
    >
      {icon}
      <span className="hidden @md:inline">{label}</span>
    </button>
  );
}

/** 包标题：从 /api/state.dungeon.packs 查；查不到回 theme_id */
function usePackTitle(themeId: string): string {
  const t = useT();
  const packs = useApp((s) => s.state?.dungeon?.packs ?? []);
  const p = packs.find((x) => x.id === themeId || x.themes.includes(themeId));
  return t(p?.title ?? themeId);
}
