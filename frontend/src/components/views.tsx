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
    ["版本", ci?.version ?? "dev"],
    ["AI 模型", ci?.model ?? "—"],
    ["主题", s?.character ?? "—"],
    ["主题设定文件", ci?.character_file ?? "—"],
    ["波形配置", ci?.waveforms_file ?? "—"],
  ];
  return (
    <div className="flex flex-col gap-3">
      <div className="rounded-[14px] border border-line bg-panel p-5">
        <h3 className="mb-3 text-[13px] font-semibold tracking-[1.5px] text-muted">当前配置</h3>
        {rows.map(([k, v]) => (
          <div key={k} className="flex justify-between border-b border-line py-2.5 text-[13px] last:border-0">
            <span className="text-muted">{k}</span>
            <span className="max-w-[60%] truncate">{v}</span>
          </div>
        ))}
        <p className="mt-3 text-[11px] leading-relaxed text-faint">
          修改 config\character.yaml（主题/示例）保存后下一条消息即生效；
          <br />
          AI 模型配置在下方填写、保存即生效；其余 config.yaml / config\waveforms.yaml 修改后需重启程序。
        </p>
      </div>
      <LlmSettings />
    </div>
  );
}

/** AI 模型配置：设置页填写 API Key / Base URL / 模型名，保存即生效（后端热加载） */
function LlmSettings() {
  const [info, setInfo] = useState<{
    base_url: string;
    model: string;
    api_key_masked: string;
    has_key: boolean;
    saved: boolean;
    json_mode: boolean;
  } | null>(null);
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [model, setModel] = useState("");
  const [jsonMode, setJsonMode] = useState(true);
  const [status, setStatus] = useState<{ kind: "ok" | "err"; text: string } | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api
      .getLlm()
      .then((v) => {
        setInfo(v);
        setBaseUrl(v.base_url);
        setModel(v.model);
        setJsonMode(v.json_mode ?? true);
      })
      .catch(() => {});
  }, []);

  const inputCls =
    "min-w-0 flex-1 rounded-lg border border-line bg-ink3 px-3 py-1.5 text-[13px] text-text outline-none transition-colors focus:border-accent";

  const save = async () => {
    setBusy(true);
    setStatus(null);
    try {
      const r = await api.setLlm({ api_key: apiKey, base_url: baseUrl, model, json_mode: jsonMode });
      setStatus({ kind: "ok", text: `已保存并生效（模型：${r.model ?? model}）` });
      setApiKey("");
      api.getLlm().then(setInfo).catch(() => {});
    } catch (e) {
      setStatus({ kind: "err", text: `保存失败：${String(e)}` });
    } finally {
      setBusy(false);
    }
  };

  const test = async () => {
    setBusy(true);
    setStatus(null);
    try {
      const r = await api.testLlm({ api_key: apiKey, base_url: baseUrl, model });
      setStatus(
        r.ok
          ? { kind: "ok", text: r.detail ?? "连接成功" }
          : { kind: "err", text: r.error ?? "连接失败" },
      );
    } catch (e) {
      setStatus({ kind: "err", text: String(e) });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="rounded-[14px] border border-line bg-panel p-5">
      <h3 className="mb-1 text-[13px] font-semibold tracking-[1.5px] text-muted">AI 模型配置</h3>
      <p className="mb-3 text-[11px] leading-relaxed text-faint">
        {info?.saved
          ? "已保存到 config.yaml，此处修改保存即生效、无需重启。"
          : "尚未保存过（当前用示例配置），首次保存后写入 config.yaml。"}
        {info?.has_key ? ` 已有密钥：${info.api_key_masked}` : " 当前无密钥。"}
      </p>
      <div className="flex flex-col gap-2.5">
        <label className="flex items-center gap-3 text-[12px] text-muted">
          <span className="w-16 flex-none">API Key</span>
          <input
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder={
              info?.has_key
                ? `已保存 ${info.api_key_masked}；粘贴新密钥覆盖，留空保存 = 清除`
                : "粘贴 API Key（留空则使用环境变量 DGLAB_LLM_API_KEY）"
            }
            className={inputCls}
          />
        </label>
        <label className="flex items-center gap-3 text-[12px] text-muted">
          <span className="w-16 flex-none">Base URL</span>
          <input value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} className={inputCls} />
        </label>
        <label className="flex items-center gap-3 text-[12px] text-muted">
          <span className="w-16 flex-none">模型名</span>
          <input value={model} onChange={(e) => setModel(e.target.value)} className={inputCls} />
        </label>
        <label className="flex items-center gap-2 text-[12px] text-muted">
          <input
            type="checkbox"
            checked={jsonMode}
            onChange={(e) => setJsonMode(e.target.checked)}
            className="h-3.5 w-3.5 accent-[#f7d97a]"
          />
          JSON 模式（部分中转站不兼容，可关闭）
        </label>
        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={() => void test()}
            disabled={busy}
            className="rounded-lg border border-line bg-panel2 px-3 py-1.5 text-[12px] transition-colors hover:border-line2 disabled:opacity-50"
          >
            测试连接
          </button>
          <button
            onClick={() => void save()}
            disabled={busy}
            className="rounded-lg bg-accent px-3 py-1.5 text-[12px] font-semibold text-ink transition-opacity disabled:opacity-50"
          >
            保存并生效
          </button>
          {status && (
            <span className={`text-[12px] ${status.kind === "ok" ? "text-accent" : "text-red-400"}`}>
              {status.text}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
