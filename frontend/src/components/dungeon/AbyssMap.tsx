/**
 * 深渊剖面图：把 render.map（chain 节点表）按层带纵向切成 5 层，越往下越深。
 * 未到过的房间只显示「？」（雾），到过的显示标题与次数，当前房间金色脉动。
 * panel 态（mid/窄面板）：默认折叠为一行「深度计」，点开展开完整剖面。
 * column 态（宽屏右栏独占）：始终展开、无折叠钮；容器铺满列高。
 * D34：band 行按内容自然高（去掉 flex-1 等分）；Boss/结局视觉权重；上一格走过短动效。
 * D35：column 态内容自然高不足时按 CSS 变量等比放大填满（上限 1.4）；过长则 s=1 可滚动。panel 保持原状。
 */
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import { useT } from "../../i18n";
import type { DungeonChainMap, DungeonMapNode } from "../../types";
import { BAND_ORDER, bandLabel, bandShort, bandTier, endingLabel, roomLabel } from "./labels";
import RoomIcon from "./RoomIcon";

export type AbyssMapMode = "panel" | "column";

/** zijin 结局事件 id → ending kind（theme_labels.endings） */
function endingKindOf(n: DungeonMapNode): string | null {
  if (n.room !== "ending") return null;
  if (n.id === "E903") return "escape";
  if (n.id === "E008") return "stay";
  if (n.id === "E007") return "sink";
  const title = n.title || "";
  if (title.includes("破渊")) return "escape";
  if (title.includes("理智")) return "stay";
  if (title.includes("欲海") || title.includes("沉沦")) return "sink";
  return null;
}

export default function AbyssMap({
  map,
  collapsedDefault = true,
  mode = "panel",
}: {
  map: DungeonChainMap;
  collapsedDefault?: boolean;
  /** panel = 可折叠（mid/窄）；column = 右栏常驻展开、铺满列高 */
  mode?: AbyssMapMode;
}) {
  const t = useT();
  const isColumn = mode === "column";
  const [open, setOpen] = useState(isColumn ? true : !collapsedDefault);
  const cur = map.nodes.find((n) => n.current) ?? map.nodes.find((n) => n.id === map.current);
  const byBand = new Map<string, DungeonMapNode[]>();
  for (const n of map.nodes) {
    const list = byBand.get(n.band) ?? [];
    list.push(n);
    byBand.set(n.band, list);
  }
  const known = BAND_ORDER as readonly string[];
  const bands = [...BAND_ORDER.filter((b) => byBand.has(b)), ...[...byBand.keys()].filter((b) => !known.includes(b))];
  const visitedCount = map.nodes.filter((n) => n.visited > 0).length;
  const showBody = isColumn || open;

  // D34 P1-2：上一格 current → visited 时短动效一次
  const prevCurRef = useRef<string | null>(null);
  const [leavingId, setLeavingId] = useState<string | null>(null);
  useEffect(() => {
    const now = cur?.id ?? map.current ?? null;
    const prev = prevCurRef.current;
    if (prev && now && prev !== now) {
      setLeavingId(prev);
      const tid = window.setTimeout(() => setLeavingId((id) => (id === prev ? null : id)), 400);
      prevCurRef.current = now;
      return () => window.clearTimeout(tid);
    }
    prevCurRef.current = now;
  }, [cur?.id, map.current]);

  // D35: column 填满缩放 — 先按 s=1 量自然高 N，再 s=clamp(1,(H*0.96)/N,1.4)
  const scrollRef = useRef<HTMLDivElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);
  const fitRafRef = useRef<number | null>(null);
  const fitScaleRef = useRef(1);

  const applyFitScale = (s: number) => {
    const el = contentRef.current;
    if (!el) return;
    fitScaleRef.current = s;
    const chipFs = Math.max(10, Math.round(11 * s * 2) / 2);
    const bandFs = Math.max(9, Math.round(10 * s * 2) / 2);
    const tierFs = Math.max(11, Math.round(13 * s * 2) / 2);
    el.style.setProperty("--dg-fit-s", String(s));
    el.style.setProperty("--dg-chip-fs", `${chipFs}px`);
    el.style.setProperty("--dg-chip-px", `${0.375 * s}rem`);
    el.style.setProperty("--dg-chip-py", `${0.125 * s}rem`);
    el.style.setProperty("--dg-chip-gap", `${0.375 * s}rem`);
    el.style.setProperty("--dg-row-py", `${0.375 * s}rem`);
    el.style.setProperty("--dg-band-fs", `${bandFs}px`);
    el.style.setProperty("--dg-band-tier-fs", `${tierFs}px`);
    el.style.setProperty("--dg-icon-size", `${Math.max(10, Math.round(11 * s * 2) / 2)}px`);
    el.style.setProperty("--dg-icon-boss-size", `${Math.max(11, Math.round(13 * s * 2) / 2)}px`);
  };

  useLayoutEffect(() => {
    if (!isColumn || !showBody) return;
    const scrollEl = scrollRef.current;
    const contentEl = contentRef.current;
    if (!scrollEl || !contentEl) return;

    const measure = () => {
      // 先回到 s=1 再量 N，避免缩放反馈环
      applyFitScale(1);
      void contentEl.offsetHeight;
      const N = contentEl.scrollHeight;
      const H = scrollEl.clientHeight;
      let s = 1;
      if (N > 0 && H > 0 && N < H * 0.95) {
        s = Math.min(1.4, Math.max(1, (H * 0.96) / N));
      }
      applyFitScale(s);
    };

    const schedule = () => {
      if (fitRafRef.current != null) cancelAnimationFrame(fitRafRef.current);
      fitRafRef.current = requestAnimationFrame(() => {
        fitRafRef.current = null;
        measure();
      });
    };

    const ro = new ResizeObserver(schedule);
    ro.observe(scrollEl);
    ro.observe(contentEl);
    schedule();
    return () => {
      ro.disconnect();
      if (fitRafRef.current != null) {
        cancelAnimationFrame(fitRafRef.current);
        fitRafRef.current = null;
      }
    };
  }, [isColumn, showBody, bands.length, map.nodes.length, map.current, visitedCount]);

  const meter = (
    <span className="flex gap-[3px]">
      {bands.map((b) => (
        <span
          key={b}
          className={`h-3 w-2 rounded-[2px] ${
            cur?.band === b
              ? "bg-accent shadow-[0_0_6px_var(--color-accent)]"
              : byBand.get(b)?.some((n) => n.visited)
                ? "bg-arcane/70"
                : "bg-ink3 ring-1 ring-line"
          }`}
        />
      ))}
    </span>
  );

  const curLine = cur && (
    <span className="truncate">
      <span className="text-accent">{bandTier(cur.band)}</span> {t(bandShort(cur.band))} · {t(roomLabel(cur.room))} ·{" "}
      <span className="text-text">{cur.title}</span>
    </span>
  );

  const explored = (
    <span className="ml-auto flex items-center gap-1 text-faint">
      {t("已探 {n}/{m}", { n: visitedCount, m: map.nodes.length })}
      {!isColumn && (open ? <ChevronUp size={12} /> : <ChevronDown size={12} />)}
    </span>
  );

  return (
    <div
      className={
        isColumn
          ? "dg-strata flex h-full min-h-0 flex-col"
          : "dg-strata flex-none border-b border-line @lg:border-b-0 @lg:border-l"
      }
    >
      {isColumn ? (
        <div className="flex w-full flex-none items-center gap-2 border-b border-line/60 px-3 py-2 text-[11px] text-muted">
          {meter}
          {curLine}
          {explored}
        </div>
      ) : (
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          className="flex w-full items-center gap-2 px-3 py-2 text-left text-[11px] text-muted hover:text-text"
        >
          {meter}
          {curLine}
          {explored}
        </button>
      )}
      {showBody && (
        <div
          ref={isColumn ? scrollRef : undefined}
          className={
            isColumn
              ? "flex min-h-0 flex-1 flex-col overflow-y-auto px-3 pb-3"
              : "px-3 pb-3"
          }
        >
          <div ref={isColumn ? contentRef : undefined} className={isColumn ? "dg-fit-scale" : undefined}>
            {bands.map((b, bi) => {
              const nodes = byBand.get(b) ?? [];
              const here = cur?.band === b;
              return (
                <div
                  key={b}
                  className={`dg-band-row flex gap-2 ${bi > 0 ? "border-t border-line/60" : ""}${
                    isColumn ? " min-h-0 items-start" : ""
                  }`}
                >
                  <div
                    className={`dg-band-label w-14 flex-none pt-1 leading-tight ${
                      here ? "text-accent" : "text-faint"
                    }`}
                  >
                    <div className="dg-band-tier font-bold">{bandTier(b)}</div>
                    <div>{t(bandLabel(b))}</div>
                  </div>
                  <div className="dg-chip-row flex flex-1 flex-wrap content-start">
                    {nodes.map((n) => (
                      <Node key={n.id} n={n} leaving={leavingId === n.id} />
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

function Node({ n, leaving }: { n: DungeonMapNode; leaving: boolean }) {
  const t = useT();
  const seen = n.visited > 0;
  const isBoss = n.room === "boss";
  const isEnding = n.room === "ending";
  const endKind = endingKindOf(n);
  const endName = endKind ? endingLabel(endKind) : "";
  const label = seen
    ? isEnding && endName
      ? endName
      : n.title
    : "？";

  let cls = n.current
    ? "dg-current border-accent bg-accent/20 text-accent"
    : seen
      ? "border-arcane/50 bg-arcane/10 text-arcane"
      : "border-line/60 text-faint";

  if (isBoss) {
    cls += " dg-boss-chip";
    if (!n.current) {
      cls = cls.replace("border-arcane/50", "border-[color:var(--color-demon)]").replace(
        "bg-arcane/10",
        "bg-[color:var(--color-demon)]/15",
      );
      if (seen && !n.current) cls = cls.replace("text-arcane", "text-[color:var(--color-demon)]");
    }
  }
  if (isEnding && seen) {
    cls += " dg-ending-chip";
  }
  if (leaving && !n.current) {
    cls += " dg-rise dg-leave-flash";
  }

  return (
    <span
      className={`dg-chip inline-flex items-center gap-1 rounded-md border ${cls}`}
      title={seen ? `${label} · ${t(roomLabel(n.room))}` : t("未探索")}
      aria-hidden={false}
    >
      <RoomIcon room={seen ? n.room : "unknown"} size={isBoss ? 13 : 11} />
      <span className={`truncate ${isBoss ? "max-w-[10rem] font-medium" : "max-w-[9rem]"}`}>{label}</span>
      {n.visited > 1 && <span className="text-[9px] opacity-70">×{n.visited}</span>}
    </span>
  );
}
