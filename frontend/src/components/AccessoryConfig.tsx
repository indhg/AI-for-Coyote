import { useEffect, useState } from "react";
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
        AI 台词里的电刺激只会出现在对应配件的位置；未工作的通道不会被描写。
      </p>
    </div>
  );
}

function ChannelAccessory({ ch }: { ch: "A" | "B" }) {
  const dev = useApp((st) => st.state?.device_channels?.[ch]);
  // 本地乐观状态：点选立即生效（避免等服务器回包时闪回旧值/待适配）
  const [name, setName] = useState(dev?.name ?? "贴片");
  const [loc, setLoc] = useState(dev?.location ?? "");
  useEffect(() => {
    if (dev?.name) setName(dev.name);
  }, [dev?.name]);
  useEffect(() => setLoc(dev?.location ?? ""), [dev?.location]);

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

  return (
    <div className="flex items-center gap-1.5">
      <span className="w-4 flex-none text-[12px] font-bold text-muted">{ch}</span>
      <select
        value={PRESETS.some((p) => p.name === name) ? name : "待适配"}
        onChange={(e) => {
          const p = PRESETS.find((x) => x.name === e.target.value) ?? PRESETS[2];
          setName(p.name);
          setLoc(p.location);
          void save({ name: p.name, location: p.location, baseline: p.baseline });
        }}
        className="w-[86px] flex-none rounded-[8px] border border-line bg-panel2 px-1.5 py-1 text-[12px] outline-none"
      >
        {PRESETS.map((p) => (
          <option key={p.name} value={p.name}>
            {p.name}
          </option>
        ))}
      </select>
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
