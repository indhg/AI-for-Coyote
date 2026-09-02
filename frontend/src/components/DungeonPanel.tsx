import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { useApp, useDungeon } from "../store";
import { useT } from "../i18n";
import type { DungeonPack, DungeonRender } from "../types";
import iconEncounter from "../assets/dungeon-icons/encounter.png";
import iconElite from "../assets/dungeon-icons/elite.png";
import iconTreasure from "../assets/dungeon-icons/treasure.png";
import iconSafe from "../assets/dungeon-icons/safe.png";
import iconCorridor from "../assets/dungeon-icons/corridor.png";
import iconBoss from "../assets/dungeon-icons/boss.png";

const FLOOR_OPTIONS = [3, 5, 7];
const LEVELS = ["轻", "中", "重"];

function consentDismissed(version: string): boolean {
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

interface TrailEntry {
  title: string;
  theme_id: string;
  kind: string;
  content_level: string;
  tier: number;
  narrative: string;
  hint: string;
  executed: string[];
  chosen: string;
}

// 开局最少主题数
const MIN_THEMES = 3;
// 地牢开跑总开关：紫金地牢尚未完工（2026-09-03 用户拍板先禁止开跑）。
// 顶栏可进大厅浏览/配主题，但「进入地牢 ▶」开跑被禁用；完工后改回 true 即恢复
// （引擎/内容/后端接口均保留）
const DUNGEON_PLAYABLE = false;
// 基础包（地牢默认元素）：强制选择、不可取消；后续可加更多
const BASE_THEMES = ["dungeon", "mark"];
// 可选主题的显示顺序（基础 → 触手 → 品评会 → 哥布林）
const DEFAULT_OPTIONAL_THEMES = ["tentacle", "appraisal", "goblin"];

export default function DungeonPanel() {
  const render = useDungeon((s) => s.render);
  const busy = useDungeon((s) => s.busy);
  const error = useDungeon((s) => s.error);
  const setRender = useDungeon((s) => s.setRender);
  const setBusy = useDungeon((s) => s.setBusy);
  const setError = useDungeon((s) => s.setError);

  const packs = useApp((s) => s.state?.dungeon?.packs ?? []);
  const version = useApp((s) => s.state?.config_info?.version ?? "");

  const [themes, setThemes] = useState<string[]>([]);
  const [floors, setFloors] = useState(5);
  const [level, setLevel] = useState("中");
  const [showConsent, setShowConsent] = useState(false);
  const [trail, setTrail] = useState<TrailEntry[]>([]);
  // 层间结算：跨层检测由主组件持续记录，纯文本事件流切换时也不会丢失层数
  const mapFloorRef = useRef<number | null>(null);
  const [restBanner, setRestBanner] = useState(false);

  function trackFloor(r: DungeonRender) {
    const nf = r.map?.floor;
    if (mapFloorRef.current != null && nf != null && nf !== mapFloorRef.current) {
      setRestBanner(true);
    }
    if (nf != null) mapFloorRef.current = nf;
  }
  // 基础包（地牢刻印 + 淫纹）强制常驻，不可取消；默认全勾（基础+触手+品评会），开局最少 3 个主题
  const themeIds = [...new Set(packs.flatMap((p) => p.themes))];
  const themesInitedRef = useRef(false);
  useEffect(() => {
    if (!themesInitedRef.current && themeIds.length > 0) {
      themesInitedRef.current = true;
      setThemes(
        [...BASE_THEMES, ...DEFAULT_OPTIONAL_THEMES].filter((t) => themeIds.includes(t)),
      );
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [themeIds.join(",")]);

  async function doStart() {
    if (!DUNGEON_PLAYABLE) return; // 地牢未完工，禁止开跑（完工后改 DUNGEON_PLAYABLE = true）
    setBusy(true);
    setError(null);
    try {
      const r = await api.dungeonStart({
        active_themes: themes,
        mix_policy: "mixed_pool",
        floors,
        map_mode: true,
      });
      setTrail([]);
      mapFloorRef.current = r.map?.floor ?? null;
      setRestBanner(false);
      setRender(r);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function doAdvance(choiceId?: string, text?: string, mapTarget?: { row: number; col: number }) {
    const cur = render;
    const chosen = choiceId
      ? (cur?.event?.choices.find((c) => c.id === choiceId)?.label ?? "")
      : (text ?? "");
    setBusy(true);
    setError(null);
    try {
      const r = await api.dungeonAdvance(
        mapTarget
          ? { map_target: mapTarget }
          : choiceId
            ? { choice_id: choiceId }
            : { text },
      );
      if (cur && cur.event && cur.narrative && !mapTarget) {
        const ev = cur.event;
        const narr = cur.narrative;
        setTrail((t) => [
          ...t,
          {
            title: ev.title,
            theme_id: ev.theme_id,
            kind: ev.kind,
            content_level: ev.content_level,
            tier: ev.tier,
            narrative: narr.text,
            hint: cur.feedback.hint,
            executed: cur.executed,
            chosen,
          },
        ]);
      }
      trackFloor(r);
      setRender(r);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function doRestart() {
    setTrail([]);
    setRender(null);
    setError(null);
    try {
      await api.dungeonRestart();
    } catch {
      /* ignore */
    }
  }

  function onStartClick() {
    if (!DUNGEON_PLAYABLE) return; // 地牢未完工：连同意卡都不弹（完工后改 DUNGEON_PLAYABLE = true）
    if (themes.length === 0) return;
    if (consentDismissed(version)) {
      void doStart();
    } else {
      setShowConsent(true);
    }
  }

  const phase = render
    ? render.run.phase === "ending"
      ? "ending"
      : "run"   // map_select 也走 run（纯文本模式自动推进，一闪而过）
    : "lobby";

  // 纯文本模式：map_select 时自动推进（后端 PRNG 自动选路，前端无地图 UI）
  useEffect(() => {
    if (render && render.map && render.run.phase === "map_select" && !busy) {
      void doAdvance();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [render, busy]);

  return (
    <aside className="dungeon-frame flex h-full min-h-0 flex-col border-r border-line bg-ink2">
      {phase === "lobby" && (
        <Lobby
          packs={packs}
          themes={themes}
          setThemes={setThemes}
          floors={floors}
          setFloors={setFloors}
          level={level}
          setLevel={setLevel}
          busy={busy}
          error={error}
          onStart={onStartClick}
        />
      )}
      {render && phase === "run" && (
        <RunView
          render={render}
          trail={trail}
          busy={busy}
          error={error}
          restBanner={restBanner}
          onDismissRest={() => setRestBanner(false)}
          onAdvance={doAdvance}
          onRestart={doRestart}
        />
      )}
      {phase === "ending" && render && (
        <EndingView render={render} trail={trail} onRestart={doRestart} />
      )}
      {showConsent && (
        <ConsentModal
          version={version}
          onCancel={() => setShowConsent(false)}
          onConfirm={(noMore) => {
            if (noMore) setConsentDismissed(version);
            setShowConsent(false);
            void doStart();
          }}
        />
      )}
    </aside>
  );
}

/* ============================== 大厅 ============================== */
function Lobby(props: {
  packs: DungeonPack[];
  themes: string[];
  setThemes: (t: string[]) => void;
  floors: number;
  setFloors: (f: number) => void;
  level: string;
  setLevel: (l: string) => void;
  busy: boolean;
  error: string | null;
  onStart: () => void;
}) {
  const t = useT();
  const { packs, themes, setThemes, floors, setFloors, level, setLevel, busy, error, onStart } = props;
  const themeIds = [...new Set(packs.flatMap((p) => p.themes))];
  // 主题 id → 中文标题（pack.title）
  const titleOf = (tid: string) => packs.find((p) => p.themes.includes(tid))?.title ?? tid;

  function toggleTheme(id: string) {
    // 基础包强制常驻，不可取消
    if (BASE_THEMES.includes(id)) return;
    setThemes(themes.includes(id) ? themes.filter((t) => t !== id) : [...themes, id]);
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-y-auto p-5 pb-20">
      <div className="mb-4">
        <h2 className="text-2xl font-bold text-accent">{t("紫金地牢")}</h2>
        <p className="mt-1 text-sm text-muted">{t("一座变幻莫测的地下城…")}</p>
      </div>

      <Section label="本局主题（至少选择 3 项）">
        {themeIds.length === 0 && <p className="text-sm text-faint">{t("暂无已装主题包")}</p>}
        <div className="flex flex-wrap gap-2">
          {/* 基础（锁定）：代表基础包集合（地牢刻印 + 淫纹），必选、不出现在可选项里 */}
          <button
            disabled
            title={t("地牢刻印、淫纹（基础包，必选）")}
            className="cursor-default rounded-lg border border-arcane bg-arcane/15 px-3.5 py-2 text-sm text-arcane"
          >
            {t("基础")}
          </button>
          {themeIds
            .filter((id) => !BASE_THEMES.includes(id))
            .sort((a, b) =>
              DEFAULT_OPTIONAL_THEMES.indexOf(a) - DEFAULT_OPTIONAL_THEMES.indexOf(b),
            )
            .map((id) => {
              const on = themes.includes(id);
              return (
                <button
                  key={id}
                  onClick={() => toggleTheme(id)}
                  className={`rounded-lg border px-3.5 py-2 text-sm transition-colors ${
                    on
                      ? "border-arcane bg-arcane/15 text-arcane"
                      : "border-line text-muted hover:border-arcane hover:text-text"
                  }`}
                >
                  {t(titleOf(id))}
                </button>
              );
            })}
        </div>
      </Section>

      <Section label="深度（层数）">
        <div className="flex flex-wrap gap-2">
          {FLOOR_OPTIONS.map((f) => (
            <button
              key={f}
              onClick={() => setFloors(f)}
              className={`rounded-lg border px-3.5 py-2 text-sm transition-colors ${
                floors === f
                  ? "border-accent2 bg-accent/10 text-accent"
                  : "border-line text-muted hover:border-accent2 hover:text-text"
              }`}
            >
              {t("{f} 层", { f })}
            </button>
          ))}
        </div>
      </Section>

      <Section label="内容封顶（本局最高分级）">
        <div className="flex flex-wrap gap-2">
          {LEVELS.map((l) => (
            <button
              key={l}
              onClick={() => setLevel(l)}
              className={`rounded-lg border px-3.5 py-2 text-sm transition-colors ${
                level === l
                  ? "border-accent2 bg-accent/10 text-accent"
                  : "border-line text-muted hover:border-accent2 hover:text-text"
              }`}
            >
              {t(l)}
            </button>
          ))}
        </div>
      </Section>

      {error && (
        <p className="mt-3 rounded-lg border border-bad/40 bg-bad/10 px-3 py-2 text-sm text-bad">
          {error}
        </p>
      )}

      <button
        onClick={onStart}
        disabled={!DUNGEON_PLAYABLE || themes.length < MIN_THEMES || busy}
        title={DUNGEON_PLAYABLE ? undefined : t("紫金地牢尚未完工，暂不能开始冒险")}
        className="mt-6 rounded-[12px] bg-accent2 px-5 py-3 text-base font-bold text-ink transition-opacity disabled:opacity-40"
      >
        {DUNGEON_PLAYABLE
          ? busy
            ? t("正在开启…")
            : themes.length < MIN_THEMES
              ? t("再选 {n} 个主题（至少 {min} 个）", {
                  n: MIN_THEMES - themes.length,
                  min: MIN_THEMES,
                })
              : t("进入地牢 ▶")
          : t("地牢建设中 · 暂未开放")}
      </button>
      <p className="mt-2 text-xs text-faint">
        {DUNGEON_PLAYABLE
          ? t("进入前需确认 18+ 同意（可勾选不再提示）")
          : t("紫金地牢尚未完工，内容打磨完成后开放")}
      </p>
    </div>
  );
}

/* ============================== 同意卡 ============================== */
function ConsentModal(props: {
  version: string;
  onCancel: () => void;
  onConfirm: (noMore: boolean) => void;
}) {
  const t = useT();
  const [agree, setAgree] = useState(false);
  const [noMore, setNoMore] = useState(false);

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/60 p-6">
      <div className="w-full max-w-md rounded-[16px] border border-line bg-panel p-6 shadow-2xl">
        <h3 className="text-lg font-bold text-accent">{t("开始前确认")}</h3>
        <ul className="mt-4 space-y-2 text-sm leading-relaxed text-text">
          <li>{t("· 虚构内容，双方成人，可随时离开")}</li>
          <li>{t("· 空格长按 / 底栏急停会立即清零设备")}</li>
          <li>{t("· 体感受本机上限与通道开关约束")}</li>
          <li>{t("· 通道字母 ≠ 身体部位")}</li>
        </ul>
        <label className="mt-5 flex items-center gap-2 text-sm text-text">
          <input type="checkbox" checked={agree} onChange={(e) => setAgree(e.target.checked)} />
          {t("我已成年且自愿")}
        </label>
        <label className="mt-2 flex items-center gap-2 text-xs text-muted">
          <input type="checkbox" checked={noMore} onChange={(e) => setNoMore(e.target.checked)} />
          {t("不再显示此提示")}
        </label>
        <div className="mt-6 flex gap-3">
          <button
            onClick={props.onCancel}
            className="flex-1 rounded-[10px] border border-line px-4 py-2.5 text-sm text-muted hover:text-text"
          >
            {t("取消")}
          </button>
          <button
            onClick={() => props.onConfirm(noMore)}
            disabled={!agree}
            className="flex-1 rounded-[10px] bg-accent2 px-4 py-2.5 text-sm font-bold text-ink disabled:opacity-40"
          >
            {t("确认进入")}
          </button>
        </div>
      </div>
    </div>
  );
}

/* ============================== 局内 ============================== */
const NODE_TYPE_ICON: Record<string, string> = {
  encounter: iconEncounter,
  elite: iconElite,
  treasure: iconTreasure,
  safe: iconSafe,
  corridor: iconCorridor,
  boss: iconBoss,
};

function RunView(props: {
  render: DungeonRender;
  trail: TrailEntry[];
  busy: boolean;
  error: string | null;
  restBanner: boolean;
  onDismissRest: () => void;
  onAdvance: (choiceId?: string, text?: string) => void;
  onRestart: () => void;
}) {
  const t = useT();
  const { render, trail, busy, error, restBanner, onDismissRest, onAdvance, onRestart } = props;
  const ev = render.event;
  const rs = render.run.run_state;
  if (!ev || !render.narrative) return null;
  const [skipped, setSkipped] = useState(false);
  const [text, setText] = useState("");
  const feedRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    feedRef.current?.scrollTo({ top: feedRef.current.scrollHeight });
  }, [trail.length, render]);

  function submitText() {
    const t = text.trim();
    if (!t) return;
    setText("");
    onAdvance(undefined, t);
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      {/* 层间结算横幅（纯文本模式：跨层后显示） */}
      {restBanner && (
        <div className="border-b border-arcane/40 bg-arcane/10 px-5 py-3">
          <p className="text-sm font-semibold text-arcane">
            {t("第 {n} 层完成", {
              n: render.map ? render.map.floor - 1 : render.run.floor_index,
            })}
          </p>
          <p className="mt-0.5 text-xs text-muted">
            {t("已走 {n} 个节点 · 热 {heat} · 本局已自动存档", {
              n: render.map?.visited_nodes.length ?? 0,
              heat: rs.heat ?? 0,
            })}
          </p>
          <button
            onClick={onDismissRest}
            className="mt-2 rounded-[8px] bg-accent2 px-3 py-1 text-xs font-semibold text-ink"
          >
            {t("下行 ↓")}
          </button>
        </div>
      )}
      {/* 顶部：层/房 + 路径条（地图模式）或楼层地图（线性模式） */}
      <div className="border-b border-line px-5 py-3">
        <div className="flex items-center justify-between">
          <span className="text-sm text-text">
            {render.map
              ? t("第 {f} 层 · 本层已走 {n} 节点", {
                  f: render.map.floor,
                  n: render.map.visited_nodes.length,
                })
              : t("第 {f} 层 · 第 {r} 房", {
                  f: render.run.floor_index,
                  r: render.run.room_index,
                })}
          </span>
          {render.map && (
            <span className="text-xs text-muted">{t("当前事件：{title}", { title: ev.title })}</span>
          )}
        </div>
        {render.map ? (
          <div className="mt-2 flex flex-wrap gap-1">
            {render.map.visited_nodes.slice(-8).map((k, i) => {
              const [r, c] = k.split(",").map(Number);
              const type = render.map!.node_types[k] ?? "?";
              return (
                <span key={i} className="rounded border border-arcane/40 bg-arcane/10 px-1.5 py-0.5 text-[10px] text-arcane">
                  <img
                    src={NODE_TYPE_ICON[type] ?? iconEncounter}
                    alt={type}
                    className="h-4 w-4 rounded-full object-cover"
                  />
                  <span>{t("·行{r}", { r })}</span>
                </span>
              );
            })}
          </div>
        ) : (
          <FloorMap run={render.run} />
        )}
      </div>

      {/* 状态条 */}
      <div className="flex flex-wrap items-center gap-x-5 gap-y-1 border-b border-line px-5 py-2 text-sm">
        <span className="text-text">HP {hearts(rs.hp)}</span>
        <span className="text-text">{t("意志 {bars}", { bars: bars(rs.will, 6) })}</span>
        {Object.keys(rs.affinity).length > 0 && (
          <span className="text-text">
            {t("亲和")}{" "}
            {Object.entries(rs.affinity)
              .map(([k, v]) => `${k} ${bars(v, 5)}`)
              .join("  ")}
          </span>
        )}
        <span className="text-muted">{t("体感[{hint}]", { hint: render.feedback.hint })}</span>
      </div>

      {/* 滚动历史流：旧事件 + 当前事件 */}
      <div ref={feedRef} className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
        {trail.map((t, i) => (
          <EventCardView key={i} entry={t} current={false} />
        ))}
        <EventCardView
          entry={{
            title: ev.title,
            theme_id: ev.theme_id,
            kind: ev.kind,
            content_level: ev.content_level,
            tier: ev.tier,
            narrative: render.narrative.text,
            hint: render.feedback.hint,
            executed: render.executed,
            chosen: "",
          }}
          current
          skipped={skipped}
          onToggleSkip={() => setSkipped((s) => !s)}
        />
        {error && (
          <p className="mt-3 rounded-lg border border-bad/40 bg-bad/10 px-3 py-2 text-sm text-bad">
            {error}
          </p>
        )}
      </div>

      {/* 选项 + 输入 */}
      <div className="border-t border-line px-5 pt-3 pb-20">
        {ev.choices.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {ev.choices.map((c) => (
              <button
                key={c.id}
                disabled={busy}
                onClick={() => onAdvance(c.id)}
                className="rounded-[10px] border border-accent2/60 bg-ink3 px-4 py-2 text-sm text-text transition-colors hover:border-accent2 hover:text-accent disabled:opacity-40"
              >
                {c.label}
              </button>
            ))}
          </div>
        )}
        {ev.free_input && (
          <div className="mt-3 flex gap-2">
            <input
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && submitText()}
              placeholder={t("描述你的行动……")}
              disabled={busy}
              className="min-w-0 flex-1 rounded-[10px] border border-line bg-field px-3 py-2 text-sm text-text outline-none focus:border-arcane disabled:opacity-40"
            />
            <button
              onClick={submitText}
              disabled={busy || !text.trim()}
              className="rounded-[10px] bg-accent2 px-4 py-2 text-sm font-semibold text-ink disabled:opacity-40"
            >
              {t("说出")}
            </button>
          </div>
        )}
        <div className="mt-3 flex items-center justify-between">
          <button onClick={onRestart} className="text-xs text-faint hover:text-muted">
            {t("回大厅（结束本局）")}
          </button>
          <span className="text-xs text-faint">{busy ? t("地牢主正在写下这一房…") : ""}</span>
        </div>
      </div>
    </div>
  );
}

/* 事件卡片（历史条目 + 当前事件复用） */
function EventCardView(props: {
  entry: TrailEntry;
  current: boolean;
  skipped?: boolean;
  onToggleSkip?: () => void;
}) {
  const t = useT();
  const { entry, current, skipped, onToggleSkip } = props;
  return (
    <div
      className={`mb-3 rounded-[14px] border bg-panel p-4 ${
        entry.kind === "boss"
          ? "border-arcane2 shadow-[0_0_20px_rgba(138,95,214,0.35)]"
          : current
            ? "border-arcane/50"
            : "border-line"
      }`}
    >
      <div className="flex items-center justify-between">
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className="rounded-md border border-arcane/50 bg-arcane/10 px-2 py-0.5 text-arcane">
            {entry.theme_id}
          </span>
          <span className="rounded-md border border-line px-2 py-0.5 text-muted">{t(kindLabel(entry.kind))}</span>
          <span className="rounded-md border border-line px-2 py-0.5 text-muted">
            {t("{level} · 第 {tier} 层", { level: t(entry.content_level), tier: entry.tier })}
          </span>
        </div>
        {current && (
          <button onClick={onToggleSkip} className="text-xs text-muted hover:text-text">
            {skipped ? t("展开描写") : t("跳过描写")}
          </button>
        )}
      </div>
      <h3 className={`mt-2 font-semibold text-text ${current ? "text-lg" : "text-base"}`}>{entry.title}</h3>
      {!(current && skipped) && (
        <p className="mt-1.5 whitespace-pre-wrap text-[15px] leading-relaxed text-text">{entry.narrative}</p>
      )}
      {current && skipped && <p className="mt-1.5 text-sm text-muted">{entry.narrative.slice(0, 24)}…</p>}

      {/* 信号输出 */}
      {entry.executed.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1 border-t border-dashed border-line pt-2">
          {entry.executed.map((e, i) => (
            <span key={i} className="rounded-md border border-line bg-panel2 px-1.5 py-0.5 text-[11px] text-accent2">
              ▶ {e}
            </span>
          ))}
        </div>
      )}
      {entry.executed.length === 0 && current && (
        <p className="mt-2 text-xs text-faint">{t("体感[{hint}]", { hint: entry.hint })}</p>
      )}

      {/* 历史条目显示玩家选择 */}
      {!current && entry.chosen && (
        <p className="mt-2 text-xs text-muted">{t("你选择了：「{chosen}」", { chosen: entry.chosen })}</p>
      )}
    </div>
  );
}

/* ============================== 结局 ============================== */
function EndingView(props: { render: DungeonRender; trail: TrailEntry[]; onRestart: () => void }) {
  const t = useT();
  const { render, trail, onRestart } = props;
  const rs = render.run.run_state;
  if (!render.event || !render.narrative) return null;
  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-y-auto p-6 pb-20">
      <div className="mx-auto w-full max-w-md">
        <div className="rounded-[16px] border border-arcane/50 bg-panel p-6 text-center shadow-[0_0_30px_rgba(138,95,214,0.25)]">
          <h2 className="text-2xl font-bold text-accent">{render.event.title}</h2>
          <p className="mt-3 whitespace-pre-wrap text-sm leading-relaxed text-text">
            {render.narrative.text}
          </p>
          <div className="mt-4 text-sm text-muted">
            {t("第 {f} 层 · 房间 {r}", {
              f: render.run.floor_index,
              r: render.run.room_index,
            })}
            <br />
            {t("HP {h} · 意志 {w}", {
              h: hearts(rs.hp),
              w: bars(rs.will, 6),
            })}
          </div>
          <p className="mt-3 text-xs text-faint">{t("体感已清理")}</p>
          <div className="mt-6 flex gap-3">
            <button
              onClick={onRestart}
              className="flex-1 rounded-[10px] bg-accent2 px-4 py-2.5 text-sm font-bold text-ink"
            >
              {t("再开一局")}
            </button>
            <button
              onClick={onRestart}
              className="flex-1 rounded-[10px] border border-line px-4 py-2.5 text-sm text-muted hover:text-text"
            >
              {t("回大厅")}
            </button>
          </div>
        </div>

        {trail.length > 0 && (
          <div className="mt-4">
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-faint">{t("本局足迹")}</p>
            {trail.map((t, i) => (
              <div key={i} className="mb-2 rounded-[10px] border border-line bg-panel p-3">
                <p className="text-sm font-medium text-text">{t.title}</p>
                <p className="mt-1 text-xs text-muted">
                  {t.narrative.slice(0, 60)}…
                </p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

/* ============================== 小部件 ============================== */
function Section(props: { label: string; children: React.ReactNode }) {
  const t = useT();
  return (
    <div className="mb-5">
      <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-faint">{t(props.label)}</p>
      {props.children}
    </div>
  );
}

function FloorMap(props: { run: DungeonRender["run"] }) {
  const { run } = props;
  const nodes = [];
  for (let f = 1; f <= run.floors; f++) {
    const isBoss = f === run.floors;
    const isCur = f === run.floor_index;
    const isDone = f < run.floor_index;
    nodes.push(
      <span
        key={f}
        className={`inline-flex h-6 w-6 items-center justify-center rounded text-xs ${
          isBoss ? "text-accent" : isCur ? "bg-arcane text-ink" : isDone ? "text-accent2" : "text-faint"
        }`}
      >
        {isBoss ? "◆" : isDone ? "●" : isCur ? "▲" : "○"}
      </span>,
    );
    if (f < run.floors) nodes.push(<span key={`l${f}`} className="text-faint">─</span>);
  }
  return <div className="mt-2 flex items-center">{nodes}</div>;
}

function hearts(hp: number): string {
  const n = Math.max(0, Math.min(10, hp));
  return "♥".repeat(n) + "♡".repeat(Math.max(0, 6 - n));
}
function bars(v: number, total: number): string {
  const n = Math.max(0, Math.min(total, v));
  return "▓".repeat(n) + "░".repeat(total - n);
}
function kindLabel(k: string): string {
  return { scene: "场景", beat: "片刻", choice: "抉择", boss: "深层", ending: "终局" }[k] ?? k;
}
