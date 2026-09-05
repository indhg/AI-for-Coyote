/**
 * 深渊路网主体（D26 / D30 正稿）：读真 render.map（mode=map）。
 * SVG 边层 + HTML 节点层 + 头部信息条 + 底部确认条；键盘 ←→ 选、Enter 确认、Esc 取消。
 * mode: column（宽屏右栏，行高 72）| panel（mid/窄底部抽屉，行高 64）。
 * 选中态与动作来自 useRouteActions（与主栏岔口卡共享）。
 */
import { useEffect, useMemo, useRef, useState } from "react";
import { useT } from "../../i18n";
import type { DungeonRouteMap } from "../../types";
import { BAND_ORDER, bandShort, bandTier, roomLabel } from "./labels";
import RouteNode from "./RouteNode";
import RouteTerminus from "./RouteTerminus";
import { ROUTE_GUTTER, ROUTE_SLOTS, ROUTE_TERMINUS_H, deriveEdgeVisual, nodeJitter, rowHeightFor } from "./routeGeom";
import type { RouteActions } from "./useRouteActions";

export default function RouteMap({ map, acts, mode = "column" }: { map: DungeonRouteMap; acts: RouteActions; mode?: "column" | "panel" }) {
  const t = useT();
  const rowH = rowHeightFor(mode);
  const scrollRef = useRef<HTMLDivElement>(null);
  const stageRef = useRef<HTMLDivElement>(null);
  const [stageW, setStageW] = useState(400);

  const { phase, ending, seed, ended, estop, awaiting, blocked, selectedNodeId, select, confirm, cancel } = acts;
  const cur = map.nodes.find((n) => n.id === map.current);
  const selected = selectedNodeId ? map.nodes.find((n) => n.id === selectedNodeId) : undefined;
  const showConfirm = awaiting && !blocked && !!selected;
  const sunk = phase === "locked" || ending === "sink";

  const bandsSeen = useMemo(() => {
    const set = new Set(map.nodes.map((n) => n.band));
    return BAND_ORDER.filter((b) => set.has(b));
  }, [map.nodes]);

  useEffect(() => {
    const el = stageRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setStageW(el.clientWidth || 400));
    ro.observe(el);
    setStageW(el.clientWidth || 400);
    return () => ro.disconnect();
  }, []);

  // 相机：current 放在容器 40% 高处（结局后不再滚）
  useEffect(() => {
    if (ended) return;
    const el = scrollRef.current;
    if (!el || !cur) return;
    const y = cur.floor * rowH + rowH * 0.5;
    el.scrollTo({ top: Math.max(0, y - el.clientHeight * 0.4), behavior: "smooth" });
  }, [map.current, ended, cur, rowH]);

  const totalH = map.floors * rowH + ROUTE_TERMINUS_H;
  const usable = Math.max(120, stageW - ROUTE_GUTTER);
  const xOf = (col: number, id: string) => ROUTE_GUTTER + ((col + 0.5) / ROUTE_SLOTS) * usable + nodeJitter(id);
  const confirmLabel = selected
    ? t("前往 · {what}", { what: `${t(roomLabel(selected.room))}${selected.title ? `「${selected.title}」` : ""}` })
    : t("前往");

  return (
    <div
      className={`dg-strata flex h-full min-h-0 flex-col outline-none ${estop ? "pointer-events-none saturate-[.4]" : ""}`}
      tabIndex={0}
      role="application"
      aria-label={t("深渊路网")}
      onKeyDown={(e) => {
        if (blocked || !awaiting) return;
        const reach = map.nodes.filter((n) => n.state === "reachable").sort((a, b) => a.col - b.col);
        if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
          e.preventDefault();
          if (!reach.length) return;
          const i = selectedNodeId ? reach.findIndex((n) => n.id === selectedNodeId) : -1;
          const next = e.key === "ArrowRight" ? (i + 1) % reach.length : (i - 1 + reach.length) % reach.length;
          if (reach[next].id !== selectedNodeId) select(reach[next].id);
        } else if (e.key === "Enter") {
          e.preventDefault();
          if (showConfirm) confirm();
        } else if (e.key === "Escape") {
          e.preventDefault();
          cancel();
        }
      }}
    >
      {/* 头部信息条 */}
      <div className="flex w-full flex-none items-center gap-2 border-b border-line/60 px-3 py-2 text-[11px] text-muted">
        <span className="flex gap-[3px]">
          {bandsSeen.map((b) => (
            <span
              key={b}
              className={`h-3 w-2 rounded-[2px] ${
                cur?.band === b
                  ? "bg-accent shadow-[0_0_6px_var(--color-accent)]"
                  : map.nodes.some((n) => n.band === b && (n.state === "visited" || n.state === "current"))
                    ? "bg-arcane/70"
                    : "bg-ink3 ring-1 ring-line"
              }`}
            />
          ))}
        </span>
        {cur && (
          <span className="min-w-0 truncate">
            {t("第 {f} / {F} 层", { f: cur.floor, F: map.floors - 1 })} · {t(bandShort(cur.band))} · {t(roomLabel(cur.room))}
            {cur.title ? ` · 「${cur.title}」` : ""}
          </span>
        )}
        <span className="ml-auto flex-none text-faint" title={seed != null ? `seed ${seed}` : undefined}>
          {t("井 #{seed}", { seed: map.seed_label })}
          {sunk ? ` · ${t("已沉")}` : ""}
        </span>
      </div>

      {/* 舞台 */}
      <div ref={scrollRef} className="relative min-h-0 flex-1 overflow-y-auto">
        <div ref={stageRef} className="relative mx-auto w-full max-w-[515px]" style={{ height: totalH, minHeight: totalH }}>
          {/* 井壁：层号 + 层带 */}
          <div className="pointer-events-none absolute bottom-0 left-0 top-0 border-r border-line/30" style={{ width: ROUTE_GUTTER }}>
            {Array.from({ length: map.floors }, (_, f) => {
              const band = map.nodes.find((n) => n.floor === f)?.band ?? "mid";
              const prev = f > 0 ? map.nodes.find((n) => n.floor === f - 1)?.band : null;
              const showBand = f === 0 || band !== prev;
              return (
                <div key={f} className="absolute left-0 px-1 text-[10px] leading-tight text-faint" style={{ top: f * rowH + 8, width: ROUTE_GUTTER }}>
                  <div className="font-bold text-muted">{f}</div>
                  {showBand && (
                    <div>
                      {bandTier(band)} {t(bandShort(band))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {/* 层带淡色 + 分隔线 */}
          {Array.from({ length: map.floors }, (_, f) => {
            const band = map.nodes.find((n) => n.floor === f)?.band ?? "mid";
            const prev = f > 0 ? map.nodes.find((n) => n.floor === f - 1)?.band : null;
            const tint =
              band === "mid" ? "rgba(185,140,242,0.04)" : band === "upper" ? "rgba(185,140,242,0.08)" : band === "lower" ? "rgba(185,140,242,0.12)" : "transparent";
            return (
              <div
                key={`tint-${f}`}
                className={`pointer-events-none absolute right-0 ${f > 0 && band !== prev ? "border-t border-line/60" : ""}`}
                style={{ left: ROUTE_GUTTER, top: f * rowH, height: rowH, background: tint }}
              />
            );
          })}

          {/* 边层 */}
          <svg className="pointer-events-none absolute inset-0" width={stageW} height={totalH} aria-hidden>
            {map.edges.map((e) => {
              const a = map.nodes.find((n) => n.id === e.from);
              const b = map.nodes.find((n) => n.id === e.to);
              if (!a || !b) return null;
              const visual = deriveEdgeVisual(map, e.from, e.to);
              const x0 = xOf(a.col, a.id);
              const y0 = a.floor * rowH + rowH / 2;
              const x1 = xOf(b.col, b.id);
              const y1 = b.floor * rowH + rowH / 2;
              const selectedOpen = selectedNodeId === e.to && visual === "open";
              const stroke =
                visual === "taken"
                  ? sunk
                    ? "var(--color-demon)"
                    : "var(--color-accent2)"
                  : visual === "open"
                    ? "var(--color-arcane)"
                    : visual === "closed"
                      ? "rgba(255,255,255,0.12)"
                      : "rgba(255,255,255,0.2)";
              const sw = visual === "taken" || selectedOpen ? 2 : visual === "open" ? 1.5 : 1;
              const dash = visual === "open" && !selectedOpen ? "4 3" : visual === "closed" ? "3 4" : undefined;
              const opacity = visual === "open" && selectedNodeId && !selectedOpen ? 0.4 : visual === "taken" && sunk ? 0.6 : 1;
              return (
                <path
                  key={`${e.from}-${e.to}`}
                  d={`M ${x0} ${y0} C ${x0} ${y0 + rowH / 3}, ${x1} ${y1 - rowH / 3}, ${x1} ${y1}`}
                  fill="none"
                  stroke={stroke}
                  strokeWidth={sw}
                  strokeDasharray={dash}
                  opacity={opacity}
                  className={visual === "open" && !selectedOpen && awaiting ? "dg-flow" : undefined}
                />
              );
            })}
          </svg>

          {/* 节点层 */}
          <div className="absolute right-0 top-0" style={{ left: ROUTE_GUTTER, bottom: ROUTE_TERMINUS_H }}>
            {map.nodes.map((n) => (
              <div key={n.id} className="absolute left-0 right-0" style={{ top: n.floor * rowH, height: rowH }}>
                <RouteNode node={n} selected={selectedNodeId === n.id} rowH={rowH} onClick={() => select(n.id)} />
              </div>
            ))}
          </div>

          {/* 三扇结局门（只读） */}
          <div className="absolute bottom-0 right-0" style={{ left: ROUTE_GUTTER, height: ROUTE_TERMINUS_H }}>
            <RouteTerminus endings={map.terminus.endings} phase={phase} ending={ending} />
          </div>
        </div>
      </div>

      {/* 底部：急停红字 / 确认条 */}
      {estop ? (
        <div className="flex h-12 flex-none items-center justify-center border-t border-bad/40 bg-bad/10 text-sm text-bad">{t("急停中，路网已锁")}</div>
      ) : showConfirm ? (
        <div className="flex h-12 flex-none items-center gap-2 border-t border-line/60 bg-panel/90 px-3">
          <span className="min-w-0 flex-1 truncate text-xs text-muted">{confirmLabel}</span>
          <button type="button" onClick={confirm} className="h-11 min-w-[4.5rem] rounded-lg bg-accent2 px-4 text-sm font-bold text-ink">
            {t("前往")}
          </button>
          <button type="button" onClick={cancel} className="h-11 rounded-lg border border-line px-3 text-sm text-muted hover:border-line2">
            {t("取消")}
          </button>
        </div>
      ) : null}
    </div>
  );
}
