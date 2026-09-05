/**
 * 深渊路网选路动作（D30）：地图节点与主栏岔口卡共用的单一入口。
 *  - select(id)：按节点态分流——reachable 进入「已选中待确认」；visited/locked/fog/gated 只出 toast（gated 返回 "gated" 让节点抖一下）
 *  - confirm()：对已选中节点调 POST /api/dungeon/move；错误经 classifyError 转 toast
 *  - cancel()：清选中
 * 选中态放 useDungeon.selectedNodeId（每帧 render 到达自动清空）。
 */
import { useCallback } from "react";
import { api } from "../../api";
import { useT } from "../../i18n";
import { useApp, useDungeon } from "../../store";
import { isRouteMap, type DungeonRouteMap, type DungeonRouteNodeState } from "../../types";
import { classifyError, gateText, setThemeLabels } from "./labels";

export interface RouteActions {
  map: DungeonRouteMap | null;
  phase: string;
  ending: string | null;
  seed: number | null;
  ended: boolean;
  estop: boolean;
  busy: boolean;
  /** 任何原因不能推进（busy / 急停 / 结局） */
  blocked: boolean;
  /** 现在正等玩家选路 */
  awaiting: boolean;
  selectedNodeId: string | null;
  select: (id: string) => DungeonRouteNodeState | string | undefined;
  confirm: () => void;
  cancel: () => void;
}

export function useRouteActions(): RouteActions {
  const t = useT();
  const render = useDungeon((s) => s.render);
  const busy = useDungeon((s) => s.busy);
  const selectedNodeId = useDungeon((s) => s.selectedNodeId);
  const setSelectedNodeId = useDungeon((s) => s.setSelectedNodeId);
  const setBusy = useDungeon((s) => s.setBusy);
  const setRender = useDungeon((s) => s.setRender);
  const setNotice = useDungeon((s) => s.setNotice);
  const estop = useApp((s) => s.state?.estop ?? false);

  const map = render && isRouteMap(render.map) ? render.map : null;
  const phase = render?.run.phase ?? "playing";
  const ending = (render?.run.ending as string | null | undefined) ?? null;
  const seed = render?.run.seed ?? null;
  const ended = phase === "ended" || phase === "locked";
  const blocked = busy || estop || ended;
  const awaiting = !!map && map.awaiting_move && !ended;

  const confirm = useCallback(() => {
    if (!map || !awaiting || blocked || !selectedNodeId) return;
    const id = selectedNodeId;
    void (async () => {
      setBusy(true);
      try {
        const r = await api.dungeonMove(id);
        setThemeLabels(r.theme_labels);
        setRender(r);
      } catch (e) {
        const c = classifyError(e instanceof Error ? e.message : String(e));
        setNotice(t(c.text));
        setSelectedNodeId(null);
      } finally {
        setBusy(false);
      }
    })();
  }, [map, awaiting, blocked, selectedNodeId, setBusy, setRender, setNotice, setSelectedNodeId, t]);

  const select = useCallback(
    (id: string): DungeonRouteNodeState | string | undefined => {
      if (!map || blocked) return undefined;
      const n = map.nodes.find((x) => x.id === id);
      if (!n) return undefined;
      switch (n.state) {
        case "reachable":
          if (!awaiting) return n.state;
          if (selectedNodeId === id) confirm(); // 再点同一节点 = 确认（D26 §3.2）
          else setSelectedNodeId(id);
          return n.state;
        case "visited":
          setNotice(t("无法回头"));
          return n.state;
        case "locked":
        case "fog":
          setNotice(t("尚不可达"));
          return n.state;
        case "gated": {
          const why = gateText(n.gate, t);
          setNotice(why ? t("被门槛拦住：{reason}", { reason: why }) : t("被门槛拦住"));
          return n.state;
        }
        default:
          return n.state;
      }
    },
    [map, blocked, awaiting, selectedNodeId, confirm, setSelectedNodeId, setNotice, t],
  );

  const cancel = useCallback(() => setSelectedNodeId(null), [setSelectedNodeId]);

  return { map, phase, ending, seed, ended, estop, busy, blocked, awaiting, selectedNodeId, select, confirm, cancel };
}
