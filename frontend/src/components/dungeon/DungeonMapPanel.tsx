/**
 * 右栏常驻地图（D24 §五 / D27 / D30）：宽屏 · 地牢局中态下独占整列。
 * 按 render.map.mode 分流：chain → AbyssMap column（一字不改）；map → RouteMap column（D30 深渊路网）。
 * column 态：始终展开、无折叠钮、铺满列高。mid/窄屏不渲染；无局返回 null（由 App 层切回设备组）。
 */
import { useDungeon, useLayout } from "../../store";
import { useT } from "../../i18n";
import { isRouteMap } from "../../types";
import AbyssMap from "./AbyssMap";
import RouteMap from "./RouteMap";
import { useRouteActions } from "./useRouteActions";

export default function DungeonMapPanel() {
  const t = useT();
  const map = useDungeon((s) => s.render?.map);
  const wide = useLayout((s) => s.mode) === "wide";
  const acts = useRouteActions();
  if (!wide || !map) return null;
  const route = isRouteMap(map);
  return (
    <section className="flex h-full min-h-0 flex-col rounded-[14px] border border-line bg-panel">
      <h3 className="flex-none border-b border-line px-3 py-2 text-[12px] font-semibold tracking-[1.5px] text-muted">
        {route ? t("深渊路网") : t("深渊剖面")}
      </h3>
      <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
        {route ? <RouteMap map={map} acts={acts} mode="column" /> : <AbyssMap map={map} mode="column" />}
      </div>
    </section>
  );
}
