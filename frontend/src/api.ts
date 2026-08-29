import type {
  ChatResult,
  FullState,
  ManualResult,
  NetworkInfo,
} from "./types";

async function j<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(path, init);
  if (!resp.ok) {
    let msg = `${resp.status} ${resp.statusText}`;
    try {
      const data = (await resp.json()) as { error?: string };
      if (data?.error) msg = data.error;
    } catch {
      /* 无 JSON 错误体时用状态码提示 */
    }
    throw new Error(msg);
  }
  return (await resp.json()) as T;
}

const json = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const api = {
  state: () => j<FullState>("/api/state"),
  chat: (message: string) => j<ChatResult>("/api/chat", json({ message })),
  manual: (action: Record<string, unknown>) =>
    j<ManualResult>("/api/manual", json(action)),
  estop: () => j<ManualResult>("/api/estop", json({})),
  resume: () => j<ManualResult>("/api/resume", json({})),
  network: () => j<NetworkInfo>("/api/network"),
  deviceChannels: (
    channels: Record<string, { name?: string; location?: string; baseline?: number }>,
  ) => j<{ ok: boolean }>("/api/device/channels", json(channels)),
  setChannelEnabled: (channel: "A" | "B", enabled: boolean) =>
    j<{ ok: boolean }>("/api/device/channels/enabled", json({ channel, enabled })),
  reportLayout: (body: { sidebar_w: number; control_w: number; inner_width: number; zoom: number }) =>
    j<{ ok: boolean; layout?: Record<string, number> }>("/api/layout", json(body)),
  setProfile: (role: string, profile: string) =>
    j<{ ok: boolean; role?: string; profile?: string }>(
      "/api/character/profile",
      json({ role, profile }),
    ),
  setNick: (nick: string) =>
    j<{ ok: boolean }>("/api/character/nick", json({ nick })),
  importDlc: (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return j<{
      ok: boolean;
      dir?: string;
      files?: string[];
      role?: string | null;
      profile?: string | null;
    }>("/api/dlc/import", { method: "POST", body: fd });
  },
  setAutopilot: (enabled: boolean) =>
    j<{ ok: boolean }>("/api/autopilot", json({ enabled })),
  getLlm: () =>
    j<{
      base_url: string;
      model: string;
      api_key_masked: string;
      has_key: boolean;
      saved: boolean;
    }>("/api/settings/llm"),
  setLlm: (body: { api_key: string; base_url: string; model: string }) =>
    j<{ ok: boolean; model?: string }>("/api/settings/llm", json(body)),
  testLlm: (body: { api_key: string; base_url: string; model: string }) =>
    j<{ ok: boolean; error?: string; detail?: string }>(
      "/api/settings/llm/test",
      json(body),
    ),
};
