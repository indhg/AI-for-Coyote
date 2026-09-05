/**
 * 紫金地牢面板（dungeon_v2 · D7 fable 版）。
 *
 * 契约权威：backend/dungeon_v2/render.py。本文件只做数据流与全局态（急停 / 成年锁 / 错误分类），
 * 视图拆在 ./dungeon/ 下：Lobby（大厅）→ RunView（剖面地图 + HUD + 正文 + 选项 + 结局 + 日志）。
 *
 * 产品铁律（整个 dungeon 面板）：
 *  - 急停态全局红条 + 选项禁用（急停来自 /api/state 的 estop，后端 advance 也会以 [estop] 拒绝）
 *  - 不显示设备强度数字 / 通道 / 波形名：executed/dropped 只用条数，不渲染 label/reason 文本
 *  - 成年锁沿用旧机制（ConsentModal + localStorage dungeon_consent_<version>）
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api";
import { useApp, useDungeon } from "../store";
import { useT } from "../i18n";
import type { DungeonRender } from "../types";
import { classifyError, setThemeLabels, type DungeonErrorKind } from "./dungeon/labels";
import Lobby from "./dungeon/Lobby";
import RunView from "./dungeon/RunView";

export const AUTOSAVE_SLOT = "autosave";

export interface PanelError {
  kind: DungeonErrorKind;
  code: string;
  text: string;
}

function consentDismissed(version: string) {
  try {
    return localStorage.getItem(`dungeon_consent_${version}`) === "1";
  } catch {
    return false;
  }
}
function setConsentDismissed(version: string) {
  try {
    localStorage.setItem(`dungeon_consent_${version}`, "1");
  } catch {
    /* ignore */
  }
}

export default function DungeonPanel() {
  const t = useT();
  const render = useDungeon((s) => s.render);
  const busy = useDungeon((s) => s.busy);
  const notice = useDungeon((s) => s.notice);
  const setRender = useDungeon((s) => s.setRender);
  const setBusy = useDungeon((s) => s.setBusy);
  const setNotice = useDungeon((s) => s.setNotice);
  const dungeonState = useApp((s) => s.state?.dungeon);
  const estop = useApp((s) => s.state?.estop ?? false);
  const version = useApp((s) => s.state?.config_info?.version ?? "");

  // 错误用结构化对象保存（store.error 是 string，这里另存以带 kind/code）
  const [error, setError] = useState<PanelError | null>(null);
  const [showConsent, setShowConsent] = useState(false);
  const pendingStart = useRef<{ pack: string | null; seed: number | null } | null>(null);

  // notice 自动消失
  useEffect(() => {
    if (!notice) return;
    const id = window.setTimeout(() => setNotice(null), 2600);
    return () => window.clearTimeout(id);
  }, [notice, setNotice]);

  const fail = useCallback((e: unknown) => {
    const msg = e instanceof Error ? e.message : String(e);
    setError(classifyError(msg));
  }, []);

  const run = useCallback(
    async (job: () => Promise<DungeonRender>) => {
      setBusy(true);
      setError(null);
      try {
        const r = await job();
        setThemeLabels(r.theme_labels); // E3：显示名优先跟后端
        setRender(r);
      } catch (e) {
        fail(e);
      } finally {
        setBusy(false);
      }
    },
    [setBusy, setRender, fail],
  );

  // E1（D11）：前端没有 render 而后端有进行中的局（页面刷新 / 切回地牢）→ 拉上一帧 render 恢复视图。
  // 只读接口，不触发设备动作；[no_run] 静默（例如刚回大厅、广播还没到）。
  const restoring = useRef(false);
  const justRestarted = useRef(false);
  const backendEvent = dungeonState?.run?.event_id ?? null;
  useEffect(() => {
    if (!backendEvent) {
      justRestarted.current = false;
      return;
    }
    if (render || restoring.current || justRestarted.current) return;
    restoring.current = true;
    (async () => {
      setBusy(true);
      try {
        const r = await api.dungeonRender();
        setThemeLabels(r.theme_labels);
        setRender(r);
      } catch (e) {
        const c = classifyError(e instanceof Error ? e.message : String(e));
        if (c.kind !== "no_run") setError(c);
      } finally {
        setBusy(false);
        restoring.current = false;
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [backendEvent, render]);

  const doStart = useCallback(
    (pack: string | null, seed: number | null) =>
      run(() =>
        api.dungeonStart({
          ...(pack ? { active_themes: [pack] } : {}),
          ...(seed !== null && Number.isFinite(seed) ? { seed } : {}),
        }),
      ),
    [run],
  );
  const start = (pack: string | null, seed: number | null) => {
    if (consentDismissed(version)) return void doStart(pack, seed);
    pendingStart.current = { pack, seed };
    setShowConsent(true);
  };
  const advance = (choiceId: string) => run(() => api.dungeonAdvance({ choice_id: choiceId }));
  const load = () => run(() => api.dungeonLoad(AUTOSAVE_SLOT));
  const save = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.dungeonSave(AUTOSAVE_SLOT);
      setNotice(t("已存档"));
    } catch (e) {
      fail(e);
    } finally {
      setBusy(false);
    }
  };
  const restart = async () => {
    justRestarted.current = true; // 广播到达前不要把旧局又恢复回来
    setRender(null);
    setError(null);
    try {
      await api.dungeonRestart();
    } catch {
      /* 回大厅失败不阻断 */
    }
  };
  /** 结局后「再开一局」：同包、新 seed */
  const again = async () => {
    const pack = render?.run.pack_id ?? null;
    await restart();
    await doStart(pack, null);
  };

  return (
    <aside className="dungeon-frame @container relative flex h-full min-h-0 flex-col border-r border-line bg-ink2">
      {/* D30：路网选路提示（无法回头 / 尚不可达 / 门槛 / move 错误）以 toast 形式浮在面板底部 */}
      {notice && render && (
        <div
          role="status"
          className="dg-rise pointer-events-none absolute bottom-20 left-1/2 z-40 max-w-[90%] -translate-x-1/2 rounded-lg border border-line bg-panel px-4 py-2 text-sm text-accent shadow-lg"
        >
          {notice}
        </div>
      )}
      {estop && (
        <div
          role="alert"
          className="flex-none border-b border-bad bg-bad px-3 py-2 text-center text-[12px] font-bold text-white"
        >
          {t("⛔ 急停中：设备已清零，地牢暂停推进——到底部按「解除急停」恢复")}
        </div>
      )}
      {!render ? (
        <Lobby
          packs={dungeonState?.packs ?? []}
          packErrors={dungeonState?.pack_errors ?? {}}
          backendRun={dungeonState?.run ?? null}
          busy={busy}
          estop={estop}
          error={error}
          onStart={start}
          onLoad={() => void load()}
          onDiscard={() => void restart()}
          onClearError={() => setError(null)}
        />
      ) : (
        <RunView
          render={render}
          busy={busy}
          estop={estop}
          error={error}
          notice={notice}
          onAdvance={(id) => void advance(id)}
          onSave={() => void save()}
          onLoad={() => void load()}
          onRestart={() => void restart()}
          onAgain={() => void again()}
          onClearError={() => setError(null)}
        />
      )}
      {showConsent && (
        <ConsentModal
          onCancel={() => {
            pendingStart.current = null;
            setShowConsent(false);
          }}
          onConfirm={(noMore) => {
            if (noMore) setConsentDismissed(version);
            setShowConsent(false);
            const p = pendingStart.current;
            pendingStart.current = null;
            void doStart(p?.pack ?? null, p?.seed ?? null);
          }}
        />
      )}
    </aside>
  );
}

/** 成年 / 自愿确认（沿用旧面板机制与文案） */
function ConsentModal({ onCancel, onConfirm }: { onCancel: () => void; onConfirm: (noMore: boolean) => void }) {
  const t = useT();
  const [agree, setAgree] = useState(false);
  const [noMore, setNoMore] = useState(false);
  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/60 p-6">
      <div className="w-full max-w-md rounded-[16px] border border-line bg-panel p-6">
        <h3 className="text-lg font-bold text-accent">{t("开始前确认")}</h3>
        <div className="mt-3 space-y-1 text-sm text-text">
          <p>{t("· 虚构内容，双方成人，可随时离开")}</p>
          <p>{t("· 空格长按 / 底栏急停会立即清零设备")}</p>
          <p>{t("· 体感输出受安全层上限约束")}</p>
        </div>
        <label className="mt-5 flex gap-2 text-sm">
          <input type="checkbox" checked={agree} onChange={(e) => setAgree(e.target.checked)} />
          {t("我已成年且自愿")}
        </label>
        <label className="mt-2 flex gap-2 text-xs text-muted">
          <input type="checkbox" checked={noMore} onChange={(e) => setNoMore(e.target.checked)} />
          {t("不再显示此提示")}
        </label>
        <div className="mt-6 flex gap-3">
          <button onClick={onCancel} className="flex-1 rounded-[10px] border border-line py-2 text-sm">
            {t("取消")}
          </button>
          <button
            onClick={() => onConfirm(noMore)}
            disabled={!agree}
            className="flex-1 rounded-[10px] bg-accent2 py-2 text-sm font-bold text-ink disabled:opacity-40"
          >
            {t("确认进入")}
          </button>
        </div>
      </div>
    </div>
  );
}
