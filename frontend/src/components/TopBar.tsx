import { useApp } from "../store";
import watermarkGold from "../assets/watermark-gold.png";

export type ViewName = "control" | "pair" | "settings" | "help";

interface Props {
  view: ViewName;
  onView: (v: ViewName) => void;
}

export default function TopBar({ view, onView }: Props) {
  const s = useApp((st) => st.state);

  const nav: { key: ViewName; label: string }[] = [
    { key: "control", label: "控制台" },
    { key: "settings", label: "设置" },
    { key: "help", label: "帮助" },
  ];

  return (
    <header className="flex h-[60px] flex-none items-center gap-4 border-b border-line bg-ink2 px-5">
      <div className="flex items-center gap-2.5 font-bold tracking-wide">
        <span className="h-2.5 w-2.5 rounded-[3px] bg-accent shadow-[0_0_10px_rgba(247,217,122,0.5)]" />
        {s?.config_info?.title ?? "郊狼 · AI 驯服师"}
        <img
          src={watermarkGold}
          alt="作者水印"
          title="Coyote in Cradle · github.com/indhg/AI-for-Coyote"
          className="h-10 w-auto opacity-80"
        />
      </div>
      <nav className="flex gap-1">
        {nav.map((n, i) => (
          <button
            key={i}
            data-tour={n.label === "设置" ? "settings-btn" : n.label === "帮助" ? "help-btn" : undefined}
            onClick={() => onView(n.key)}
            className={`rounded-lg px-3.5 py-2 text-sm transition-colors ${
              view === n.key ? "bg-ink3 text-accent" : "text-muted hover:bg-ink3 hover:text-text"
            }`}
          >
            {n.label}
          </button>
        ))}
      </nav>
      <div className="flex-1" />
      {s?.update?.available && s.update.url ? (
        <a
          href={s.update.url}
          target="_blank"
          rel="noreferrer"
          title={`新版本 ${s.update.latest}，点击前往下载`}
          className="inline-flex items-center rounded-full border border-bad/60 bg-bad/15 px-3.5 py-1.5 text-xs font-semibold text-bad transition-colors hover:bg-bad/25"
        >
          亟待更新…
        </a>
      ) : null}
    </header>
  );
}
