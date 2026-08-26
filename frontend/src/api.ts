import type {
  ChatResult,
  FullState,
  ManualResult,
  NetworkInfo,
} from "./types";

async function j<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(path, init);
  if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText}`);
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
  setChannelScale: (channel: "A" | "B", scale: number) =>
    j<{ ok: boolean }>("/api/device/channels/scale", json({ channel, scale })),
  setProfile: (profile: string) =>
    j<{ ok: boolean }>("/api/character/profile", json({ profile })),
  setNick: (nick: string) =>
    j<{ ok: boolean }>("/api/character/nick", json({ nick })),
  setAutopilot: (enabled: boolean) =>
    j<{ ok: boolean }>("/api/autopilot", json({ enabled })),
};
