import { useEffect, useRef, useState } from "react";
import { Check, ChevronDown, ChevronUp } from "lucide-react";
import { api } from "../api";
import { useApp } from "../store";

/** 配件预设：选类型自动带出默认位置与强度基准（敏感配件基准低） */
const PRESETS: { name: string; location: string; baseline: number }[] = [
  { name: "贴片", location: "小穴", baseline: 15 },
  { name: "肛塞", location: "后穴", baseline: 5 },
  { name: "待适配", location: "", baseline: 0 },
];

export default function AccessoryConfig() {
  return (
    <div className="mt-3 rounded-[14px] border border-line bg-panel p-3.5">
      <div className="mb-2 text-[12px] font-semibold tracking-[1.5px] text-muted">配件设置</div>
      <div className="flex flex-col gap-2">
        <ChannelAccessory ch="A" />
        <ChannelAccessory ch="B" />
      </div>
      <p className="mt-2 text-[11px] leading-relaxed text-faint">
        改动称谓的时候记得敲回车（Enter）
        <br />
        未工作的通道不会被描写。
      </p>
    </div>
  );
}

function ChannelAccessory({ ch }: { ch: "A" | "B" }) {
  const dev = useApp((st) => st.state?.device_channels?.[ch]);
  // 本地乐观状态：点选立即生效（避免等服务器回包时闪回旧值/待适配）
  const [name, setName] = useState(dev?.name ?? "贴片");
  const [loc, setLoc] = useState(dev?.location ?? "");
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (dev?.name) setName(dev.name);
  }, [dev?.name]);
  useEffect(() => setLoc(dev?.location ?? ""), [dev?.location]);

  // 点浮窗外部收起
  useEffect(() => {
    if (!open) return;
    const onDown = (ev: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(ev.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  const save = async (next: { name?: string; location?: string; baseline?: number }) => {
    const payload: Record<string, { name?: string; location?: string; baseline?: number }> = {
      [ch]: {
        name: next.name ?? name,
        location: next.location ?? loc,
        ...(next.baseline !== undefined ? { baseline: next.baseline } : {}),
      },
    };
    try {
      await api.deviceChannels(payload);
    } catch {
      /* 状态由 ws 推送刷新 */
    }
  };

  const pick = (p: (typeof PRESETS)[number]) => {
    setName(p.name);
    setLoc(p.location);
    setOpen(false);
    void save({ name: p.name, location: p.location, baseline: p.baseline });
  };

  return (
    <div ref={rootRef} className="relative flex items-center gap-1.5">
      <span className="w-4 flex-none text-[12px] font-bold text-muted">{ch}</span>
      <span className="relative flex-none">
        <button
          onClick={() => setOpen((v) => !v)}
          title="更换配件"
          className="flex w-[86px] items-center justify-between rounded-[8px] border border-line bg-panel2 px-1.5 py-1 text-[12px] transition-colors hover:border-line2"
        >
          <span className="truncate">{name}</span>
          {open ? (
            <ChevronUp size={12} className="flex-none text-faint" />
          ) : (
            <ChevronDown size={12} className="flex-none text-faint" />
          )}
        </button>
        {open && (
          <div className="absolute left-1/2 top-full z-40 mt-1 flex w-24 -translate-x-1/2 flex-col gap-0.5 rounded-[8px] border border-line bg-panel p-1 shadow-xl shadow-black/60">
            {PRESETS.map((p) => (
              <button
                key={p.name}
                onClick={() => pick(p)}
                className={`flex items-center justify-center gap-1 rounded-[6px] px-2 py-1.5 text-[12px] transition-colors ${
                  p.name === name ? "bg-accent/15 text-text" : "text-muted hover:bg-panel2"
                }`}
              >
                <span>{p.name}</span>
                {p.name === name && <Check size={12} className="flex-none text-accent" />}
              </button>
            ))}
          </div>
        )}
      </span>
      <input
        value={loc}
        placeholder="位置（如 大腿根内侧）"
        onChange={(e) => setLoc(e.target.value)}
        onBlur={() => void save({ location: loc })}
        onKeyDown={(e) => {
          if (e.key === "Enter") (e.target as HTMLInputElement).blur();
        }}
        className="min-w-0 flex-1 rounded-[8px] border border-line bg-panel2 px-2 py-1 text-[12px] outline-none"
      />
    </div>
  );
}
