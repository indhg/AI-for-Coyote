import { useEffect, useState } from "react";
import { api } from "../api";
import { useApp } from "../store";
import { TOURS } from "../onboarding";
import { useT } from "../i18n";
import type { NetworkInfo } from "../types";

export function PairView() {
  const t = useT();
  const s = useApp((st) => st.state);
  const [net, setNet] = useState<NetworkInfo | null>(null);
  const [qrErr, setQrErr] = useState(false);
  const [qrTick, setQrTick] = useState(0); // 重试计数（作 img key 强制重载，避免每次渲染都带 ?t= 新请求）
  const [qrRetries, setQrRetries] = useState(0); // 自动重试最多 6 次
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

  // 二维码失败或 relay 尚未就绪时低频自动重试，最多 6 次；避免服务异常时无限请求
  useEffect(() => {
    if (paired || qrRetries >= 6 || (!qrErr && s?.relay?.controller_id)) return;
    const timer = window.setTimeout(() => {
      setQrRetries((n) => n + 1);
      setQrTick((n) => n + 1);
    }, 4000);
    return () => window.clearTimeout(timer);
  }, [paired, qrErr, qrRetries, s?.relay?.controller_id]);

  return (
    <div className="rounded-[14px] border border-line bg-panel p-5">
      <h3 className="mb-4 text-[13px] font-semibold tracking-[1.5px] text-muted">
        {t("App 配对（同一 Wi-Fi，DG-LAB 4.0 扫码）")}
      </h3>
      {s?.relay?.controller_id ? (
        qrErr ? (
          <div className="mx-auto mb-3 flex h-[200px] w-[200px] flex-col items-center justify-center gap-1 rounded-[14px] border border-line bg-ink3 px-3 text-center text-sm text-muted">
            <span>{t("二维码加载失败")}</span>
            <button
              onClick={() => {
                setQrErr(false);
                setQrRetries(0);
                setQrTick((n) => n + 1);
              }}
              className="rounded-md border border-line px-2 py-0.5 text-[11px] text-accent/80 hover:border-line2 hover:text-accent"
            >
              {t("重试（4 秒后自动）")}
            </button>
          </div>
        ) : (
          <img
            key={qrTick}
            src="/api/qrcode.png"
            alt={t("二维码")}
            className="mx-auto mb-3 block h-[200px] w-[200px] rounded-[14px] bg-white"
            onLoad={() => setQrErr(false)}
              onError={() => setQrErr(true)}
          />
        )
      ) : (
            <div className="mx-auto mb-3 flex h-[200px] w-[200px] flex-col items-center justify-center gap-1 rounded-[14px] border border-line bg-ink3 px-3 text-center text-sm text-muted">
              <span>{t(qrRetries >= 6 ? "中继服务仍未就绪" : "等待中继连接…")}</span>
              <span className="text-[11px] text-faint">
                {t(qrRetries >= 6 ? "请确认服务后点击重试" : "二维码会低频自动重试")}
              </span>
            </div>
      )}
      <p className="mx-auto max-w-[420px] whitespace-pre-wrap break-all text-center text-xs leading-relaxed text-muted">
        {paired
          ? t("已在线 {n} 台；新设备请重扫上方二维码", { n: clients })
          : t("用 DG-LAB 4.0 App 扫上方二维码配对（同一 Wi-Fi）")}
        {t("\n当前电脑 IP: {ip}", { ip: net?.lan_ip ?? "…" })}
        {net && net.all_ips.length > 1 ? t("\n其他 IP: {list}", { list: net.all_ips.join(" / ") }) : ""}
      </p>
    </div>
  );
}

export function SettingsView() {
  const t = useT();
  const s = useApp((st) => st.state);
  const [intervalDraft, setIntervalDraft] = useState(12);
  const [intervalStatus, setIntervalStatus] = useState("");
  const ci = s?.config_info;
  useEffect(() => {
    if (typeof s?.autopilot_interval_s === "number") setIntervalDraft(s.autopilot_interval_s);
  }, [s?.autopilot_interval_s]);
  const saveInterval = async (value: number) => {
    setIntervalStatus(t("保存中…"));
    try {
      await api.setAutopilotInterval(value);
      setIntervalStatus(t("已生效"));
    } catch {
      setIntervalStatus(t("保存失败，请重试"));
    }
  };
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
        <h3 className="mb-3 text-[13px] font-semibold tracking-[1.5px] text-muted">{t("当前配置")}</h3>
        {rows.map(([k, v]) => (
          <div key={k} className="flex justify-between border-b border-line py-2.5 text-[13px] last:border-0">
            <span className="text-muted">{t(k)}</span>
            <span className="max-w-[60%] truncate">{t(v)}</span>
          </div>
        ))}
        <div className="mt-4 border-t border-line pt-3">
          <div className="flex items-center justify-between text-[13px]">
            <span className="text-muted">{t("AI 自动运行间隔")}</span>
            <span className="font-semibold text-text">{intervalDraft} {t("秒/轮")}</span>
          </div>
          <input
            type="range"
            min="5"
            max="30"
            step="1"
            value={intervalDraft}
            onChange={(e) => setIntervalDraft(Number(e.target.value))}
            onMouseUp={() => void saveInterval(intervalDraft)}
            onTouchEnd={() => void saveInterval(intervalDraft)}
            className="mt-2 w-full accent-accent"
            aria-label={t("AI 自动运行间隔")}
          />
          <div className="flex justify-between text-[10px] text-faint">
            <span>5 {t("秒/轮")}</span>
            <span>30 {t("秒/轮")}</span>
          </div>
          <p className="mt-1 text-[10px] text-faint">{t(intervalStatus)}</p>
        </div>
        <p className="mt-3 text-[11px] leading-relaxed text-faint">
          {t("修改 config\\character.yaml（主题/示例）保存后下一条消息即生效；")}
          <br />
          {t("AI 模型配置在下方填写、保存即生效；其余 config.yaml / config\\waveforms.yaml 修改后需重启程序。")}
        </p>
        <p className="mt-2 text-[11px] text-faint">
          <a
            href="https://x.com/cinnanirch"
            target="_blank"
            rel="noreferrer"
            className="text-accent/80 transition-colors hover:text-accent"
          >
            {t("作者主页: x.com/cinnanirch")}
          </a>
        </p>
        <UpdateRow />
      </div>
      <LlmSettings />
    </div>
  );
}

/** 帮助视图：点顶栏「帮助」时右侧显示（公告重看 + 新手引导 + 更新状态；后续扩充进阶指引/FAQ 等）。 */
export function HelpView({
  onReplayTour,
  onShowNotice,
}: {
  onReplayTour: () => void;
  onShowNotice: () => void;
}) {
  const t = useT();
  const s = useApp((st) => st.state);
  const ci = s?.config_info;
  return (
    <div className="flex flex-col gap-3">
      <div className="rounded-[14px] border border-line bg-panel p-5">
        <h3 className="mb-3 text-[13px] font-semibold tracking-[1.5px] text-muted">{t("帮助")}</h3>
        <div className="flex flex-col gap-2.5">
          <button
            onClick={onShowNotice}
            className="w-fit rounded-lg border border-accent/60 bg-accent/15 px-3.5 py-1.5 text-[12px] font-semibold text-accent transition-colors hover:bg-accent/25"
          >
            {t("公告")}
          </button>
          <button
            onClick={() => {
              try {
                localStorage.removeItem(`tour_done_${TOURS[0].id}_${ci?.version ?? ""}`);
              } catch {
                /* 隐私模式或禁用存储时直接重新打开引导 */
              }
              onReplayTour();
            }}
            className="w-fit rounded-lg border border-accent/60 bg-accent/15 px-3.5 py-1.5 text-[12px] font-semibold text-accent transition-colors hover:bg-accent/25"
          >
            {t("新手引导")}
          </button>
          {s?.update?.available && s.update.url ? (
            <a
              href={s.update.url}
              target="_blank"
              rel="noreferrer"
              className="text-[12px] font-semibold text-bad transition-colors hover:underline"
            >
              {t("亟待更新：{latest}，点击下载 →", { latest: s.update.latest })}
            </a>
          ) : (
            <span className="text-[11px] text-faint">{t("已是最新版本")}</span>
          )}
          <span className="mt-1 text-[11px] text-faint">{t("更多帮助内容（进阶指引、FAQ）即将上线。")}</span>
        </div>
      </div>
    </div>
  );
}

/** AI 模型配置：设置页填写 API Key / Base URL / 模型名，保存即生效（后端热加载） */
function LlmSettings() {
  const t = useT();
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
      setStatus({ kind: "ok", text: t("已保存并生效（模型：{model}）", { model: r.model ?? model }) });
      setApiKey("");
      api.getLlm().then(setInfo).catch(() => {});
    } catch (e) {
      setStatus({ kind: "err", text: t("保存失败：{e}", { e: String(e) }) });
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
          ? { kind: "ok", text: r.detail ?? t("连接成功") }
          : { kind: "err", text: r.error ?? t("连接失败") },
      );
    } catch (e) {
      setStatus({ kind: "err", text: String(e) });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="rounded-[14px] border border-line bg-panel p-5">
      <h3 className="mb-1 text-[13px] font-semibold tracking-[1.5px] text-muted">{t("AI 模型配置")}</h3>
      <p className="mb-3 text-[11px] leading-relaxed text-faint">
        {t(info?.saved
          ? "已保存到 config.yaml，此处修改保存即生效、无需重启。"
          : "尚未保存过（当前用示例配置），首次保存后写入 config.yaml。")}
        {info?.has_key ? t(" 已有密钥：{masked}", { masked: info.api_key_masked }) : t(" 当前无密钥。")}
      </p>
      <div className="flex flex-col gap-2.5">
        <label className="flex items-center gap-3 text-[12px] text-muted">
          <span className="w-16 flex-none">API Key</span>
          <input
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            data-tour="api-key"
            placeholder={
              info?.has_key
                ? t("已保存 {masked}；粘贴新密钥覆盖，留空保存 = 清除", { masked: info.api_key_masked })
                : t("粘贴 API Key（留空则使用环境变量 DGLAB_LLM_API_KEY）")
            }
            className={inputCls}
          />
        </label>
        <label className="flex items-center gap-3 text-[12px] text-muted">
          <span className="w-16 flex-none">Base URL</span>
          <input value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} data-tour="base-url" className={inputCls} />
        </label>
        <label className="flex items-center gap-3 text-[12px] text-muted">
          <span className="w-16 flex-none">{t("模型名")}</span>
          <input value={model} onChange={(e) => setModel(e.target.value)} data-tour="model" className={inputCls} />
        </label>
        <label className="flex items-center gap-2 text-[12px] text-muted">
          <input
            type="checkbox"
            checked={jsonMode}
            onChange={(e) => setJsonMode(e.target.checked)}
            className="h-3.5 w-3.5 accent-[#f7d97a]"
          />
          {t("JSON 模式（部分中转站不兼容，可关闭）")}
        </label>
        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={() => void test()}
            disabled={busy}
            data-tour="test-btn"
            className="rounded-lg border border-line bg-panel2 px-3 py-1.5 text-[12px] transition-colors hover:border-line2 disabled:opacity-50"
          >
            {t("测试连接")}
          </button>
          <button
            onClick={() => void save()}
            disabled={busy}
            data-tour="save-btn"
            className="rounded-lg bg-accent px-3 py-1.5 text-[12px] font-semibold text-ink transition-opacity disabled:opacity-50"
          >
            {t("保存并生效")}
          </button>
          {status && (
            <span className={`text-[12px] ${status.kind === "ok" ? "text-accent" : "text-red-400"}`}>
              {t(status.text)}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

/** 更新检测行：开关 + 发现新版本时给跳转链接。 */
function UpdateRow() {
  const t = useT();
  const u = useApp((st) => st.state?.update);
  const [busy, setBusy] = useState(false);
  const toggle = async () => {
    if (!u || busy) return;
    setBusy(true);
    try {
      await api.setUpdateCheck(!u.enabled);
    } catch {
      /* 状态由 ws 推送刷新 */
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-line pt-3">
      <label className="flex items-center gap-2 text-[11px] text-muted">
        <input
          type="checkbox"
          checked={u?.enabled ?? true}
          onChange={() => void toggle()}
          disabled={busy}
          className="h-3.5 w-3.5 accent-[#f7d97a]"
        />
        {t("自动检查更新")}
      </label>
      {u?.available && u.url ? (
        <a
          href={u.url}
          target="_blank"
          rel="noreferrer"
          className="text-[11px] font-semibold text-accent hover:underline"
        >
          {t("发现新版本 {latest}，点击下载 →", { latest: u.latest })}
        </a>
      ) : (
        <span className="text-[11px] text-faint">
          {t(
            u?.enabled
              ? u?.latest
                ? "已是最新（{latest}）"
                : "尚未检查到更新"
              : "更新检查已关闭（版本锁定）",
            u?.latest ? { latest: u.latest } : undefined,
          )}
        </span>
      )}
    </div>
  );
}
