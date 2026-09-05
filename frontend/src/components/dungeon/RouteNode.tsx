/** 深渊路网 · 单节点（D26 §1.3 / §2.1）。读真 render.map 节点；gated 点击抖动；aria 全套。 */
import { useEffect, useState } from "react";
import { useT } from "../../i18n";
import type { DungeonRouteNode } from "../../types";
import RoomIcon from "./RoomIcon";
import { gateText, roomLabel, routeStateLabel } from "./labels";
import { ROUTE_SLOTS, nodeJitter } from "./routeGeom";

export default function RouteNode({
  node,
  selected,
  rowH,
  onClick,
}: {
  node: DungeonRouteNode;
  selected: boolean;
  rowH: number;
  /** 返回节点态，gated 时本组件抖一下 */
  onClick: () => string | undefined;
}) {
  const t = useT();
  const [shake, setShake] = useState(false);
  useEffect(() => {
    if (!shake) return;
    const id = window.setTimeout(() => setShake(false), 220);
    return () => window.clearTimeout(id);
  }, [shake]);

  const isBoss = node.room === "boss";
  const isAltar = node.floor === 0 && node.room === "rest";
  const size = isBoss ? 52 : isAltar ? 36 : 40;
  const showTitle = (node.state === "current" || node.state === "visited") && !!node.title;
  const title = showTitle ? truncate(node.title ?? "", 6) : "";
  const fog = !node.revealed;

  const base =
    node.state === "current"
      ? "dg-current border-accent bg-accent/20 text-accent"
      : node.state === "reachable"
        ? `border-arcane bg-arcane/10 text-arcane ${selected ? "ring-2 ring-accent2 !border-accent2" : "dg-breathe"}`
        : node.state === "gated"
          ? "border-arcane bg-arcane/10 text-arcane"
          : node.state === "visited"
            ? "border-arcane/60 bg-arcane/15 text-text"
            : node.state === "bypassed"
              ? "border-dashed border-line/40 text-faint opacity-40"
              : "border-line/60 bg-ink3 text-faint";

  const shape = isAltar ? "rounded-full" : "rounded-[10px]";
  const inert = node.state === "current" || node.state === "bypassed";
  const gateWhy = node.state === "gated" ? gateText(node.gate, t) : "";
  const tip =
    node.state === "visited"
      ? t("无法回头")
      : node.state === "locked" || fog
        ? t("尚不可达")
        : node.state === "gated"
          ? gateWhy
            ? t("被门槛拦住：{reason}", { reason: gateWhy })
            : t("被门槛拦住")
          : `${t(roomLabel(node.room))}${node.title ? ` · ${node.title}` : ""}`;

  return (
    <button
      type="button"
      onClick={() => {
        const s = onClick();
        if (s === "gated") setShake(true);
      }}
      disabled={inert}
      aria-label={t("第 {f} 层 · {room} · {state}", { f: node.floor, room: t(roomLabel(node.room)), state: t(routeStateLabel(node.state)) })}
      aria-pressed={selected || undefined}
      className={`absolute flex flex-col items-center outline-none focus-visible:[&>span:first-child]:ring-2 focus-visible:[&>span:first-child]:ring-accent ${
        inert ? "cursor-default" : "cursor-pointer"
      }${shake ? " dg-shake" : ""}`}
      style={{
        left: `calc(${((node.col + 0.5) / ROUTE_SLOTS) * 100}% + ${nodeJitter(node.id)}px)`,
        top: rowH / 2,
        transform: "translate(-50%, -50%)",
        width: Math.max(44, size + 8),
        minHeight: 44,
        padding: 4,
      }}
      title={tip}
    >
      <span
        className={`relative flex items-center justify-center border-2 ${shape} ${base}${
          isBoss ? " shadow-[inset_0_0_8px_rgba(214,92,255,0.45)] !border-demon" : ""
        }${isAltar && node.state !== "current" ? " !border-ok/70" : ""}`}
        style={{ width: size, height: size }}
      >
        <RoomIcon room={fog ? "unknown" : node.room} size={isBoss ? 22 : 18} />
        {node.state === "gated" && (
          <span className="absolute -right-1 -top-1 rounded bg-bad px-0.5 text-[9px] leading-none text-ink">{t("锁")}</span>
        )}
      </span>
      {title && <span className="mt-0.5 max-w-[4.5rem] truncate text-[11px] text-muted">{title}</span>}
    </button>
  );
}

function truncate(s: string, n: number): string {
  return s.length > n ? s.slice(0, n) + "…" : s;
}
