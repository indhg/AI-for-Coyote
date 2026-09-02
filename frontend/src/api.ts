import type {
  ChatResult,
  DungeonRender,
  DungeonState,
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
  clearHistory: () => j<{ ok: boolean }>("/api/history/clear", json({})),
  network: () => j<NetworkInfo>("/api/network"),
  deviceChannels: (
    channels: Record<string, { name?: string; location?: string; baseline?: number }>,
  ) => j<{ ok: boolean }>("/api/device/channels", json(channels)),
  setChannelEnabled: (channel: "A" | "B", enabled: boolean) =>
    j<{ ok: boolean }>("/api/device/channels/enabled", json({ channel, enabled })),
  setChannelCap: (channel: "A" | "B", value: number) =>
    j<{ ok: boolean; user_caps?: Record<string, number> }>(
      "/api/device/channels/cap",
      json({ channel, value }),
    ),
  reportLayout: (body: { sidebar_w: number; control_w: number; inner_width: number; zoom: number }) =>
    j<{ ok: boolean; layout?: Record<string, number> }>("/api/layout", json(body)),
  setSensor: (key: "camera" | "audio", enabled: boolean) =>
    j<{ ok: boolean; sensors?: { camera: boolean; audio: boolean } }>(
      "/api/sensors",
      json({ [key]: enabled }),
    ),
  setProfile: (role: string, profile: string) =>
    j<{ ok: boolean; role?: string; profile?: string }>(
      "/api/character/profile",
      json({ role, profile }),
    ),
  setIntensity: (level: string) =>
    j<{ ok: boolean; intensity_level?: string; strength_scale?: Record<string, number> }>(
      "/api/intensity",
      json({ level }),
    ),
  setNick: (nick: string) =>
    j<{ ok: boolean }>("/api/character/nick", json({ nick })),
  setLang: (lang: "zh" | "en") =>
    j<{ ok: boolean; lang?: string; en_available?: boolean }>(
      "/api/character/lang",
      json({ lang }),
    ),
  setAutopilot: (enabled: boolean) =>
    j<{ ok: boolean }>("/api/autopilot", json({ enabled })),
  setAutopilotInterval: (interval_s: number) =>
    j<{ ok: boolean; interval_s: number }>("/api/autopilot/interval", json({ interval_s })),
  testMode: (enabled: boolean) =>
    j<{ ok: boolean; test_mode: boolean }>("/api/test_mode", json({ enabled })),
  getLlm: () =>
    j<{
      base_url: string;
      model: string;
      api_key_masked: string;
      has_key: boolean;
      saved: boolean;
      json_mode: boolean;
    }>("/api/settings/llm"),
  setLlm: (body: { api_key: string; base_url: string; model: string; json_mode: boolean }) =>
    j<{ ok: boolean; model?: string }>("/api/settings/llm", json(body)),
  testLlm: (body: { api_key: string; base_url: string; model: string }) =>
    j<{ ok: boolean; error?: string; detail?: string }>(
      "/api/settings/llm/test",
      json(body),
    ),
  updateCheck: () =>
    j<{ enabled: boolean; latest: string; url: string; available: boolean }>("/api/update"),
  setUpdateCheck: (enabled: boolean) =>
    j<{ ok: boolean; enabled: boolean; latest: string; url: string; available: boolean }>(
      "/api/update",
      json({ enabled }),
    ),
  // ---------- 地牢 ----------
  dungeonState: () => j<DungeonState>("/api/dungeon/state"),
  dungeonStart: (body: {
    active_themes?: string[];
    mix_policy?: string;
    floors?: number;
    seed?: number;
    map_mode?: boolean;
  }) => j<DungeonRender>("/api/dungeon/start", json(body)),
  dungeonAdvance: (body: { choice_id?: string; text?: string; map_target?: { row: number; col: number } }) =>
    j<DungeonRender>("/api/dungeon/advance", json(body)),
  dungeonSave: (slot: string) =>
    j<{ ok: boolean; path: string }>("/api/dungeon/save", json({ slot })),
  dungeonLoad: (slot: string) => j<DungeonRender>("/api/dungeon/load", json({ slot })),
  dungeonRestart: () => j<{ ok: boolean }>("/api/dungeon/restart", json({})),
};
