/** 大厅：选主题包 → 进入；可读自动存档；显示后端遗留局提示与包加载错误。 */
import { useEffect, useState } from "react";
import { Dices, FolderOpen, TriangleAlert } from "lucide-react";
import { useT } from "../../i18n";
import type { DungeonPack, DungeonRun } from "../../types";
import type { PanelError } from "../DungeonPanel";
import ErrorBox from "./ErrorBox";

interface Props {
  packs: DungeonPack[];
  packErrors: Record<string, string>;
  backendRun: DungeonRun | null;
  busy: boolean;
  estop: boolean;
  error: PanelError | null;
  onStart: (pack: string | null, seed: number | null) => void;
  onLoad: () => void;
  onDiscard: () => void;
  onClearError: () => void;
}

export default function Lobby({ packs, packErrors, backendRun, busy, estop, error, onStart, onLoad, onDiscard, onClearError }: Props) {
  const t = useT();
  const [pack, setPack] = useState<string | null>(null);
  const [seedText, setSeedText] = useState("");
  useEffect(() => {
    if (!pack && packs.length) setPack(packs[0].id);
    if (pack && !packs.some((p) => p.id === pack)) setPack(packs[0]?.id ?? null);
  }, [packs, pack]);
  const seed = seedText.trim() === "" ? null : Number(seedText.trim());
  const seedBad = seed !== null && !Number.isInteger(seed);
  const canStart = !!pack && !busy && !estop && !seedBad;
  const errEntries = Object.entries(packErrors);
  const staleRun = backendRun && backendRun.phase === "playing";
  const current = packs.find((p) => p.id === pack) ?? packs[0];

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-y-auto p-5 pb-24">
      <h2 className="text-2xl font-bold text-accent">{current ? t(current.title) : t("紫金地牢 demo")}</h2>
      {current?.description && <p className="mt-1 text-sm text-muted">{t(current.description)}</p>}

      <Section label={t("主题包")}>
        {packs.length === 0 ? (
          <p className="text-sm text-faint">{t("暂无已装主题包")}</p>
        ) : (
          <div className="grid gap-2 @md:grid-cols-2">
            {packs.map((p) => {
              const on = p.id === pack;
              return (
                <button
                  key={p.id}
                  onClick={() => setPack(p.id)}
                  className={`rounded-[12px] border p-3 text-left transition-colors ${
                    on ? "border-arcane bg-arcane/15" : "border-line hover:border-line2"
                  }`}
                >
                  <p className={`text-sm font-semibold ${on ? "text-arcane" : "text-text"}`}>{t(p.title)}</p>
                  <p className="mt-1 text-[11px] text-muted">
                    {t("{n} 个事件", { n: p.event_count })}
                    {p.version ? ` · v${p.version}` : ""}
                  </p>
                </button>
              );
            })}
          </div>
        )}
        {errEntries.length > 0 && (
          <div className="mt-2 rounded-lg border border-warn/40 bg-warn/10 p-2 text-[11px] text-warn">
            <p className="flex items-center gap-1 font-semibold">
              <TriangleAlert size={12} /> {t("有主题包未能加载")}
            </p>
            {errEntries.map(([k, v]) => (
              <p key={k} className="mt-0.5 break-all text-warn/90">
                {k}: {v}
              </p>
            ))}
          </div>
        )}
      </Section>

      <Section label={t("种子（可选）")}>
        <div className="flex items-center gap-2">
          <Dices size={16} className="text-faint" />
          <input
            value={seedText}
            onChange={(e) => setSeedText(e.target.value)}
            inputMode="numeric"
            placeholder={t("留空 = 随机")}
            className={`w-40 rounded border bg-field px-3 py-1.5 text-sm ${seedBad ? "border-bad" : "border-line"}`}
          />
          <span className="text-[11px] text-faint">{t("种子决定初始数值与命运...")}</span>
        </div>
      </Section>

      {staleRun && busy && (
        <div className="mb-4 rounded-lg border border-arcane/40 bg-arcane/10 p-3 text-sm text-arcane">{t("正在恢复上一局…")}</div>
      )}
      {staleRun && !busy && (
        <div className="mb-4 rounded-lg border border-arcane/40 bg-arcane/10 p-3 text-sm">
          <p className="font-semibold text-arcane">{t("后端里还有一局没结束喵~")}</p>
          <p className="mt-1 text-xs text-muted">
            {t("自动恢复没有成功。可以读取自动存档继续，或放弃它重新开始。")}
          </p>
          <div className="mt-2 flex gap-2">
            <button onClick={onLoad} disabled={busy} className="rounded-lg border border-line px-3 py-1.5 text-xs hover:border-line2 disabled:opacity-40">
              {t("读取自动存档")}
            </button>
            <button onClick={onDiscard} disabled={busy} className="rounded-lg border border-line px-3 py-1.5 text-xs text-muted hover:border-line2 disabled:opacity-40">
              {t("放弃那一局")}
            </button>
          </div>
        </div>
      )}

      {error && <ErrorBox error={error} onClose={onClearError} onNew={() => onStart(pack, seed)} />}

      <div className="mt-2 flex flex-wrap items-center gap-3">
        <button
          onClick={() => onStart(pack, seed)}
          disabled={!canStart}
          className="rounded-[12px] bg-accent2 px-5 py-3 font-bold text-ink disabled:opacity-40"
        >
          {busy ? t("正在开启…") : estop ? t("急停中，无法进入") : t("进入地牢 ▶")}
        </button>
        {!staleRun && (
          <button
            onClick={onLoad}
            disabled={busy}
            className="flex items-center gap-1.5 rounded-[12px] border border-line px-4 py-3 text-sm text-muted hover:border-line2 hover:text-text disabled:opacity-40"
          >
            <FolderOpen size={14} /> {t("读取自动存档")}
          </button>
        )}
      </div>
      <p className="mt-4 text-[11px] leading-relaxed text-faint">{t("进入后默认关闭自动运行。急停（长按空格 / 底部按钮）随时清零设备并暂停地牢。")}</p>
    </div>
  );
}

function Section({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="mb-5 mt-4">
      <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-faint">{label}</p>
      {children}
    </div>
  );
}
