import { useEffect, useState } from "react";
import { api } from "../api";
import { useApp } from "../store";
import type { NetworkInfo } from "../types";

export function PairView() {
  const s = useApp((st) => st.state);
  const [net, setNet] = useState<NetworkInfo | null>(null);
  const paired = s?.relay?.status === "paired";
  const clients = s?.relay?.clients?.length ?? 0;

  useEffect(() => {
    const load = async () => {
      try {
        setNet(await api.network());
      } catch {
        setNet(null);
      }
    };
    load();
    const timer = setInterval(load, 15000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="rounded-[14px] border border-line bg-panel p-5">
      <h3 className="mb-4 text-[13px] font-semibold tracking-[1.5px] text-muted">
        App 配对（同一 Wi-Fi，DG-LAB 4.0 扫码）
      </h3>
      {s?.relay?.controller_id ? (
        <img src={"/api/qrcode.png?t=" + Date.now()} alt="二维码" className="mx-auto mb-3 block h-[200px] w-[200px] rounded-[14px] bg-white" />
      ) : (
        <div className="mx-auto mb-3 flex h-[200px] w-[200px] items-center justify-center rounded-[14px] border border-line bg-ink3 text-sm text-muted">
          等待中继连接…
        </div>
      )}
      <p className="mx-auto max-w-[420px] whitespace-pre-wrap break-all text-center text-xs leading-relaxed text-muted">
        {paired ? `已在线 ${clients} 台；新设备重扫：\n` : "用 DG-LAB 4.0 App 扫码：\n"}
        {net?.pair_url ?? ""}
        {"\n当前电脑 IP: " + (net?.lan_ip ?? "…")}
        {net && net.all_ips.length > 1 ? "\n其他 IP: " + net.all_ips.join(" / ") : ""}
      </p>
    </div>
  );
}

export function SettingsView() {
  const s = useApp((st) => st.state);
  const ci = s?.config_info;
  const rows: [string, string][] = [
    ["AI 模型", ci?.model ?? "—"],
    ["角色", s?.character ?? "—"],
    ["角色设定文件", ci?.character_file ?? "—"],
    ["波形配置", ci?.waveforms_file ?? "—"],
  ];
  return (
    <div className="rounded-[14px] border border-line bg-panel p-5">
      <h3 className="mb-3 text-[13px] font-semibold tracking-[1.5px] text-muted">当前配置</h3>
      {rows.map(([k, v]) => (
        <div key={k} className="flex justify-between border-b border-line py-2.5 text-[13px] last:border-0">
          <span className="text-muted">{k}</span>
          <span className="max-w-[60%] truncate">{v}</span>
        </div>
      ))}
      <p className="mt-3 text-[11px] leading-relaxed text-faint">
        修改 config\character.yaml（角色/示例）保存后下一条消息即生效；
        <br />
        修改 config.yaml / config\waveforms.yaml 后需重启程序。
      </p>
    </div>
  );
}
