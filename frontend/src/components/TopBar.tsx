import { useApp } from "../store";
import { useT } from "../i18n";
import watermarkGold from "../assets/watermark-gold.png";

export type ViewName = "control" | "pair" | "settings" | "help";
export type BoardName = "chat" | "dungeon";

interface Props {
  view: ViewName;
  onView: (v: ViewName) => void;
  board: BoardName;
  onBoard: (b: BoardName) => void;
}

export default function TopBar({ view, onView, board, onBoard }: Props) {
  const s = useApp((st) => st.state);
  const t = useT();

  const nav: { key: ViewName; label: string }[] = [
    { key: "control", label: "控制台" },
    { key: "settings", label: "设置" },
    { key: "help", label: "帮助" },
  ];

  return (
    <header className="flex h-[60px] flex-none items-center gap-4 border-b border-line bg-ink2 px-5">
      <div className="flex items-center gap-2.5 font-bold tracking-wide">
        <span className="h-2.5 w-2.5 rounded-[3px] bg-accent shadow-[0_0_10px_rgba(247,217,122,0.5)]" />
        {s?.config_info?.title ?? t("郊狼 · AI 驯服师")}
        <img
          src={watermarkGold}
          alt={t("作者水印")}
          title={t("Coyote in Cradle · 作者原创")}
          className="h-10 w-auto opacity-80"
        />
      </div>
      <nav className="flex gap-1">
        <button
          onClick={() => {
            onBoard("dungeon");
            onView("control");
          }}
          className={`rounded-lg px-3.5 py-2 text-sm transition-colors ${
            board === "dungeon"
              ? "dungeon-glow text-arcane"
              : "dungeon-entry text-arcane hover:text-[#d6c4ff]"
          }`}
        >
          {t("进入地牢")}
        </button>
        <span className="mx-1 h-5 w-[2px] self-center rounded-full bg-line2" aria-hidden="true" />
        {nav.map((n) => {
          const active =
            n.key === "control" ? board === "chat" && view === "control" : view === n.key;
          return (
            <button
              key={n.key}
              data-tour={n.key === "settings" ? "settings-btn" : n.key === "help" ? "help-btn" : undefined}
              onClick={() => {
                if (n.key === "control") onBoard("chat");
                onView(n.key);
              }}
              className={`rounded-lg border px-3.5 py-2 text-sm transition-colors ${
                active
                  ? "border-line2 bg-ink3 text-accent"
                  : "border-transparent text-muted hover:bg-ink3 hover:text-text"
              }`}
            >
              {t(n.label)}
            </button>
          );
        })}
      </nav>
      <div className="flex-1" />
      {s?.update?.available && s.update.url ? (
        <a
          href={s.update.url}
          target="_blank"
          rel="noreferrer"
          title={t("新版本 {latest}，点击前往下载", { latest: s.update.latest })}
          className="inline-flex items-center rounded-full border border-bad/60 bg-bad/15 px-3.5 py-1.5 text-xs font-semibold text-bad transition-colors hover:bg-bad/25"
        >
          {t("亟待更新…")}
        </a>
      ) : null}
    </header>
  );
}
