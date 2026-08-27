import { Plus, Settings, ShieldAlert, SlidersHorizontal } from "lucide-react";
import { doEstop } from "../commands";
import { useApp } from "../store";
import type { ViewName } from "./TopBar";
import AccessoryConfig from "./AccessoryConfig";
import CharacterConfig from "./CharacterConfig";

interface Props {
  view: ViewName;
  onView: (v: ViewName) => void;
}

export default function Sidebar({ view, onView }: Props) {
  const state = useApp((s) => s.state);
  const relay = state?.relay;
  const st = relay?.status ?? "disconnected";
  const client = relay?.clients?.[0];
  const devName = client?.devices?.[0]?.name ?? "郊狼 3.0";
  const online = st === "paired";
  const props = (client?.props ?? {}) as Record<string, unknown>;
  const chips: string[] = [];
  if (client?.slotId) chips.push("slot " + client.slotId.slice(0, 8));
  if (typeof props.power === "number") chips.push(`电量 ${props.power}%`);
  if (typeof props.channelAStatus === "number") chips.push(`A口状态 ${props.channelAStatus}`);
  if (typeof props.channelBStatus === "number") chips.push(`B口状态 ${props.channelBStatus}`);

  return (
    <aside className="overflow-y-auto border-r border-line bg-ink2 p-4">
      <div className={`mb-3.5 rounded-[14px] border border-line bg-panel p-3.5 ${online ? "" : ""}`}>
        <div className="flex items-center gap-2 text-[15px] font-semibold">
          <span className={`h-2 w-2 rounded-full ${online ? "bg-ok shadow-[0_0_8px_var(--color-ok)]" : "bg-faint"}`} />
          {devName}
        </div>
        <div className="mt-1 text-xs text-muted">
          {online ? "已连接" : st === "waiting" ? "等待配对" : "未连接"}
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

      <div className="flex flex-col gap-1">
        <SideBtn icon={<SlidersHorizontal size={16} />} label="控制台" active={view === "control"} onClick={() => onView("control")} />
        <SideBtn icon={<Plus size={16} />} label="添加 / 配对设备" active={view === "pair"} onClick={() => onView("pair")} />
        <SideBtn icon={<Settings size={16} />} label="设置" active={view === "settings"} onClick={() => onView("settings")} />
        <SideBtn icon={<ShieldAlert size={16} />} label="急停（长按空格）" danger onClick={doEstop} />
      </div>

      <AccessoryConfig />

      <CharacterConfig />

      <p className="mt-3 px-3 text-[11px] leading-relaxed text-faint">
        强度与波形均受安全上限钳制；
        <br />
        急停（长按空格 / 底部按钮）可随时清零。
      </p>
    </aside>
  );
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
