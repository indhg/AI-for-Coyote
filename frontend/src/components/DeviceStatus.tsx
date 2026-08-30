import { AlertTriangle, Mic, Video } from "lucide-react";
import { api } from "../api";
import { useApp } from "../store";

function Seg({
  k,
  v,
  valueClass = "text-[14px]",
  accent = false,
}: {
  k?: string;
  v: string;
  valueClass?: string;
  accent?: boolean;
}) {
  return (
    <span className="flex min-w-0 items-baseline gap-1">
      {k && <span className="flex-none text-[11px] text-muted">{k}</span>}
      <span
        className={`truncate font-semibold leading-tight ${valueClass} ${accent ? "text-accent" : ""}`}
        title={v}
      >
        {v}
      </span>
    </span>
  );
}

export default function DeviceStatus() {
  const s = useApp((st) => st.state);
  const st = s?.relay?.status ?? "disconnected";
  const paired = st === "paired";
  const waveOf = (ch: "A" | "B") =>
    !s?.pulse_active?.[ch] ? "空闲" : s?.patterns?.[ch] ?? "播放中";
  // 音量显示：相对「惨叫档」的百分比（后端 level_pct；旧版无此字段时回退原始电平×100）
  const audioPct = s?.audio?.running
    ? Math.max(0, Math.min(100, s.audio.level_pct ?? Math.round((s.audio.level ?? 0) * 100)))
    : 0;
  const acc = (ch: "A" | "B") => {
    const d = s?.device_channels?.[ch];
    const name = d?.name ?? "未设置";
    const loc = d?.location?.trim();
    return loc ? `${name} · ${loc}` : name;
  };

  const camOn = s?.sensors?.camera ?? false;
  const micOn = s?.sensors?.audio ?? false;
  const sensorsOn = s?.sensors_on ?? false;
  const camRunning = s?.camera?.has_frame ?? false;
  const micRunning = s?.audio?.running ?? false;
  // 警示：开关开 + 总闸开 + 实际没跑且有错误 → 显示具体原因
  const camErr = camOn && !camRunning && !!s?.camera?.error ? s.camera.error : "";
  const micErr = micOn && !micRunning && !!s?.audio?.error ? s.audio.error : "";
  const toggleSensor = async (key: "camera" | "audio") => {
    try {
      await api.setSensor(key, key === "camera" ? !camOn : !micOn);
    } catch {
      /* 状态由 ws 推送刷新 */
    }
  };
  // B 方案：按钮颜色反映真实运行状态——灰=关（或自动运行未开）/ 绿=开且在跑 / 橙=开但没跑（警示）
  type SensorVisual = "off" | "on" | "warn";
  const visualOf = (on: boolean, running: boolean): SensorVisual => {
    if (!on || !sensorsOn) return "off";
    return running ? "on" : "warn";
  };
  const sensorBtn = (
    on: boolean,
    icon: React.ReactNode,
    label: string,
    key: "camera" | "audio",
    running: boolean,
    errText: string,
  ) => {
    const visual = visualOf(on, running);
    const title =
      errText ||
      (visual === "on"
        ? `点击关闭${label}`
        : on && !sensorsOn
          ? `自动运行未开启，${label}不会启动（开启自动运行后生效）`
          : visual === "warn"
            ? `${label}启动中…`
            : `点击开启${label}`);
    const cls =
      visual === "on"
        ? "border-emerald-500/60 bg-emerald-500/15 text-emerald-300"
        : visual === "warn"
          ? "border-warn/60 bg-warn/15 text-warn"
          : "border-line bg-ink3 text-faint hover:text-muted";
    return (
      <button
        onClick={() => void toggleSensor(key)}
        title={title}
        className={`flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[11px] font-semibold transition-colors ${cls}`}
      >
        {icon}
        {label}
        {visual === "warn" && <AlertTriangle size={11} className="flex-none" />}
      </button>
    );
  };

  return (
    <div className="flex min-h-0 flex-none flex-col rounded-[14px] border border-line bg-panel p-3">
      <h3 className="mb-2 flex-none text-[12px] font-semibold tracking-[1.5px] text-muted">设备状态</h3>
      <div className="flex min-h-0 flex-1 flex-col gap-1.5">
        {/* 第一行：连接 + 传感器开关（左侧）；麦克风音量条（右侧，放不下自动换行） */}
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 rounded-xl border border-line bg-panel2 px-4 py-2">
          <span className="flex items-center gap-1.5">
            <span
              className={`flex items-center gap-1.5 rounded-md border px-2 py-0.5 text-[12px] font-bold ${
                paired
                  ? "border-emerald-500/60 bg-emerald-500/15 text-emerald-300"
                  : "border-bad/60 bg-bad/15 text-bad"
              }`}
            >
              <span
                className={`h-1.5 w-1.5 rounded-full ${
                  paired ? "bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.6)]" : "bg-bad"
                }`}
              />
              {paired ? "已连接" : "未连接"}
            </span>
            {sensorBtn(camOn, <Video size={12} />, "摄像头", "camera", camRunning, camErr)}
            {sensorBtn(micOn, <Mic size={12} />, "麦克风", "audio", micRunning, micErr)}
          </span>
          <span className="ml-auto flex items-center gap-2">
            <span className="flex-none text-[11px] text-muted">麦克风</span>
            <div className="h-[8px] w-16 flex-none overflow-hidden rounded-full bg-ink3">
              <div
                className="h-full rounded-full bg-accent transition-all"
                style={{ width: `${audioPct}%` }}
              />
            </div>
            <span className="w-6 flex-none text-right text-[12px] font-semibold tabular-nums">
              {audioPct}
            </span>
            <span
              className="w-16 flex-none truncate text-[11px] text-faint"
              title={!micRunning && micOn && !sensorsOn ? "自动运行未开启，麦克风未启动" : undefined}
            >
              {micRunning
                ? s?.audio?.last_text || "监听中…"
                : micOn && !sensorsOn
                  ? "未运行"
                  : micOn && sensorsOn && !micErr
                    ? "启动中…"
                    : "未开启"}
            </span>
          </span>
        </div>
        {/* A/B 通道行：固定列宽网格，两行各列严格对齐 */}
        {(["A", "B"] as const).map((ch) => (
          <div
            key={ch}
            className="grid grid-cols-[3rem_5.5rem_6.5rem_1fr] items-baseline gap-3 rounded-xl border border-line bg-panel2 px-4 py-2"
          >
            <span className="text-[13px] font-bold">{ch} 通道</span>
            <Seg k="强度" v={`${s?.current[ch] ?? 0} / ${s?.effective_caps?.[ch] ?? 100}`} accent />
            <Seg k="波形" v={waveOf(ch)} />
            <Seg v={acc(ch)} valueClass="text-[13px]" />
          </div>
        ))}
      </div>
    </div>
  );
}
