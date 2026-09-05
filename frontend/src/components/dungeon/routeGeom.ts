/** 深渊路网几何与边态推导（D26 §1.2 / §2.2）。纯函数，无 React。 */
import type { DungeonRouteMap } from "../../types";

/** 井壁 gutter 宽（层号 + 层带名） */
export const ROUTE_GUTTER = 44;
/** 每层横向槽位数（引擎 col 0..3） */
export const ROUTE_SLOTS = 4;
/** 结局门行高 */
export const ROUTE_TERMINUS_H = 56;

/** 节点确定性微抖动（装饰，±3px；同 id 同偏移） */
export function nodeJitter(id: string): number {
  let h = 0;
  for (let i = 0; i < id.length; i++) h = (h * 31 + id.charCodeAt(i)) | 0;
  return (h % 7) - 3;
}

export type EdgeVisual = "taken" | "open" | "closed" | "future";

/** 边 4 态由节点态 + path 推出（引擎只给 from/to） */
export function deriveEdgeVisual(map: DungeonRouteMap, from: string, to: string): EdgeVisual {
  const path = map.path;
  for (let i = 0; i < path.length - 1; i++) {
    if (path[i] === from && path[i + 1] === to) return "taken";
  }
  const fromNode = map.nodes.find((n) => n.id === from);
  const toNode = map.nodes.find((n) => n.id === to);
  if (from === map.current && toNode && (toNode.state === "reachable" || toNode.state === "gated")) return "open";
  const curFloor = map.nodes.find((n) => n.id === map.current)?.floor ?? 0;
  if (toNode?.state === "bypassed" || (fromNode && fromNode.floor < curFloor && !path.includes(from))) return "closed";
  return "future";
}

export function rowHeightFor(mode: "column" | "panel"): number {
  return mode === "column" ? 72 : 64;
}
