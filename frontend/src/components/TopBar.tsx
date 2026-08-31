import { useApp } from "../store";
import watermarkGold from "../assets/watermark-gold.png";

export type ViewName = "control" | "pair" | "settings";

interface Props {
  view: ViewName;
  onView: (v: ViewName) => void;
}

export default function TopBar({ view, onView }: Props) {
  const s = useApp((st) => st.state);
  const relay = s?.relay;
  const st = relay?.status ?? "disconnected";
  const relayText =
    { disconnected: "未连接", connecting: "连接中", waiting: "等待 App", paired: "已配对" }[st] ?? st;
  const clients = relay?.clients?.length ?? 0;

  const nav: { key: ViewName; label: string }[] = [
    { key: "control", label: "控制台" },
    { key: "settings", label: "设置" },
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
        {nav.map((n) => (
          <button
            key={n.key}
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
      <Pill cls={st === "paired" ? "ok" : st === "disconnected" ? "off" : "warn"} text={`中继: ${relayText}`} />
      <Pill cls={clients ? "ok" : "off"} text={`App: ${clients ? clients + " 台在线" : "未接入"}`} />
      <Pill cls={s?.estop ? "off" : "ok"} text={`急停: ${s?.estop ? "已触发" : "否"}`} />
    </header>
  );
}

function Pill({ cls, text }: { cls: "ok" | "off" | "warn"; text: string }) {
  const color = cls === "ok" ? "text-accent border-line2" : cls === "off" ? "text-bad border-bad/50" : "text-warn border-warn/50";
  const dot = cls === "ok" ? "bg-accent shadow-[0_0_8px_var(--color-accent)]" : cls === "off" ? "bg-bad" : "bg-warn";
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border border-line bg-ink3 px-3 py-1.5 text-xs ${color}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${dot}`} />
      {text}
    </span>
  );
}
