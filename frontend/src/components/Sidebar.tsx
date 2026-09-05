import { Plus, Settings, ShieldAlert, SlidersHorizontal } from "lucide-react";
import { doEstop } from "../commands";
import { useApp, useDungeon } from "../store";
import { useT } from "../i18n";
import type { ViewName, BoardName } from "./TopBar";
import AccessoryConfig from "./AccessoryConfig";
import CharacterConfig from "./CharacterConfig";
import RoleCard from "./RoleCard";
import { markLabel } from "./dungeon/labels";

interface Props {
  view: ViewName;
  onView: (v: ViewName) => void;
  board: BoardName;
}

export default function Sidebar({ view, onView, board }: Props) {
  const state = useApp((s) => s.state);
  const t = useT();
  const relay = state?.relay;
  const st = relay?.status ?? "disconnected";
  const client = relay?.clients?.[0];
  const devName = client?.devices?.[0]?.name ?? "郊狼 3.0";
  const online = state?.connected === true || st === "paired" || st === "ready";
  const props = (client?.props ?? {}) as Record<string, unknown>;
  const chips: string[] = [];
  if (client?.slotId) chips.push("slot " + client.slotId.slice(0, 8));
  if (typeof props.power === "number") chips.push(t("电量 {n}%", { n: props.power }));
  if (typeof props.channelAStatus === "number")
    chips.push(t("A口状态 {n}", { n: props.channelAStatus }));
  if (typeof props.channelBStatus === "number")
    chips.push(t("B口状态 {n}", { n: props.channelBStatus }));

  return (
    <aside className="h-full min-h-0 overflow-y-auto border-r border-line bg-ink2 p-4">
      <div className={`mb-3.5 rounded-[14px] border border-line bg-panel p-3.5 ${online ? "" : ""}`}>
        <div className="flex items-center gap-2 text-[15px] font-semibold">
          <span className={`h-2 w-2 rounded-full ${online ? "bg-ok shadow-[0_0_8px_var(--color-ok)]" : "bg-faint"}`} />
          {devName}
        </div>
        <div className="mt-1 text-xs text-muted">
          {online ? t("已连接") : st === "waiting" ? t("等待配对") : t("未连接")}
        </div>
        {chips.length > 0 && (
          <div className="mt-2.5 flex flex-wrap gap-1.5">
            {chips.map((c) => (
              <span key={c} className="rounded-md border border-line bg-ink3 px-2 py-1 text-[11px] text-muted">
                {c}
              </span>
            ))}
          </div>
        )}
      </div>

      {board === "dungeon" ? <DungeonRunCard /> : <RoleCard />}

      <div className="flex flex-col gap-1">
        <SideBtn icon={<SlidersHorizontal size={16} />} label={t("控制台")} active={view === "control"} onClick={() => onView("control")} />
        <SideBtn icon={<Plus size={16} />} label={t("添加 / 配对设备")} active={view === "pair"} onClick={() => onView("pair")} />
        <SideBtn icon={<Settings size={16} />} label={t("设置")} active={view === "settings"} onClick={() => onView("settings")} />
        <SideBtn icon={<ShieldAlert size={16} />} label={t("急停（长按空格）")} danger onClick={doEstop} />
      </div>

      <AccessoryConfig />

      {board !== "dungeon" && <CharacterConfig />}

      <p className="mt-3 px-3 text-[11px] leading-relaxed text-faint">
        {t("所有体感均受安全上限钳制；")}
        <br />
        {t("急停（长按空格 / 底部按钮）可随时清零。")}
      </p>
    </aside>
  );
}

/* ---------- 地牢模式：左栏「本局信息」（dungeon_v2 · D7 fable） ----------
 * 字段全部来自 render.run（run.snapshot 拍平）。这里只放面板 HUD 之外的概览：
 * 包名 / 种子 / 位置 / 身体 / 三轴 / 三维 / 淫纹 / 骰子。不含设备信息。 */
function DungeonRunCard() {
  const render = useDungeon((s) => s.render);
  const t = useT();
  const dungeonPacks = useApp((s) => s.state?.dungeon?.packs ?? []);

  if (!render) {
    return (
      <div className="mb-3.5 rounded-[14px] border border-arcane/40 bg-panel p-3.5">
        <p className="text-sm font-semibold text-arcane">{t("紫金地牢 demo")}</p>
        <p className="mt-1 text-xs text-muted">{t("在大厅选好主题包后进入")}</p>
      </div>
    );
  }

  const run = render.run;
  const ev = render.event;
  const pack = dungeonPacks.find((p) => p.id === run.pack_id || p.themes.includes(ev.theme_id));
  const ended = run.phase === "ended" || run.phase === "locked";
  return (
    <div className="mb-3.5 rounded-[14px] border border-arcane/40 bg-panel p-3.5">
      <p className="flex items-center justify-between text-sm font-semibold text-arcane">
        {t("本局信息")}
        <span className="text-[11px] text-muted">Seed {String(run.seed).slice(0, 8)}</span>
      </p>
      <div className="mt-2.5 space-y-1.5 text-xs text-muted">
        <div className="flex flex-wrap gap-1.5">
          <span className="rounded-md border border-arcane/50 bg-arcane/10 px-2 py-0.5 text-arcane">{t(pack?.title ?? ev.theme_id)}</span>
          {ended && (
            <span className={`rounded-md border px-2 py-0.5 ${run.phase === "locked" ? "border-bad/50 text-bad" : "border-accent/50 text-accent"}`}>
              {run.phase === "locked" ? t("已沉没锁定") : t("已结束")}
            </span>
          )}
        </div>
        <p className="pt-1 text-text">
          {ev.title}
          <span className="text-faint"> · {t("回合 {n}", { n: run.turn })}</span>
        </p>
        <p className="text-text">
          HP {bars(run.hp, 10)} {run.hp}
        </p>
        <p className="text-text">
          MP {bars(run.mp, 10)} {run.mp}
        </p>
        <p className="text-text">
          {t("淫化 {n}", { n: run.yin_hua })} · {t("恶堕 {n}", { n: run.e_duo })} · {t("魔化 {n}", { n: run.ma })}
        </p>
        <p className="text-text">
          {t("力量")} {run.str} · {t("敏捷")} {run.dex} · {t("智慧")} {run.int}
        </p>
        <p>
          {t("淫纹 {stage}", { stage: t(markLabel(run.mark_stage)) })} · {run.dice_name}
          {run.defeats > 0 && <span> · {t("败北 {n}", { n: run.defeats })}</span>}
        </p>
      </div>
    </div>
  );
}

function bars(v: number, total: number): string {
  const n = Math.max(0, Math.min(total, v));
  return "▓".repeat(n) + "░".repeat(total - n);
}

function SideBtn({
  icon,
  label,
  active,
  danger,
  onClick,
}: {
  icon: React.ReactNode;
  label: string;
  active?: boolean;
  danger?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`flex w-full items-center gap-2.5 rounded-[10px] px-3 py-2.5 text-left text-[13px] transition-colors ${
        danger
          ? "bg-bad font-semibold text-white hover:bg-[#ff6b83]"
          : active
            ? "bg-ink3 text-accent"
            : "text-muted hover:bg-ink3 hover:text-text"
      }`}
    >
      {icon}
      {label}
    </button>
  );
}
