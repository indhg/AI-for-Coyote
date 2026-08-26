// ---------- 与后端 /api/state 等接口对齐的类型 ----------
export interface RelayDevice {
  slotId: string;
  name: string;
  type: string;
}
export interface RelayClientInfo {
  clientId: string;
  slotId: string | null;
  devices: RelayDevice[];
  props: Record<string, unknown>;
  slotState: Record<string, unknown>;
}
export interface RelayState {
  status: "disconnected" | "connecting" | "waiting" | "paired" | string;
  controller_id: string | null;
  url: string;
  clients: RelayClientInfo[];
  last_error: string;
}
export interface PresetInfo {
  name: string;
  waveform: string;
  label: string;
  default_duration_s: number;
  max_duration_s: number;
  category: string;
  frames: string[];
}
export interface ChannelDevice {
  name: string;
  location: string;
}
export interface FullState {
  estop: boolean;
  caps: Record<"A" | "B", number>;
  effective_caps: Record<"A" | "B", number>;
  app_caps: Record<"A" | "B", number | null>;
  current: Record<"A" | "B", number>;
  requested: Record<"A" | "B", number | null>;
  pulse_active: Record<"A" | "B", boolean>;
  overheat: Record<"A" | "B", boolean>;
  device_channels: Record<"A" | "B", ChannelDevice>;
  active_channels: Record<"A" | "B", boolean>;
  enabled_channels: Record<"A" | "B", boolean>;
  strength_scale: Record<"A" | "B", number>;
  baseline_strength: Record<"A" | "B", number>;
  patterns: Record<"A" | "B", string | null>;
  profile: string;
  profiles: string[];
  profile_available: Record<string, boolean>;
  autopilot: boolean;
  autopilot_interval_s: number;
  sensors_on: boolean;
  max_pulse_s: number;
  max_temp_s: number;
  max_step: number;
  presets: PresetInfo[];
  playback: {
    frame_ms: number;
    min_duration_s: number;
    max_duration_s: number;
    loop_batch_s: number;
    loop_overlap_s: number;
  };
  ui: { quick_strengths: number[]; default_temp_s: number; default_pulse_s: number };
  dry_run: boolean;
  relay_status: string;
  controller_id: string | null;
  connected: boolean;
  notes: string[];
  camera_enabled: boolean;
  camera: Record<string, unknown>;
  audio: {
    enabled: boolean;
    running: boolean;
    last_text: string;
    last_ts: number;
    level: number;
    threshold: number;
    model_size: string;
    error: string;
  };
  relay: RelayState;
  character: string;
  config_info: {
    model: string;
    safeword: string;
    character_file: string;
    waveforms_file: string;
    title: string;
    profile: string;
    player_nick: string;
  };
}

export interface ExecutedItem {
  label: string;
  reason: string;
  sent: boolean;
}
export interface DroppedItem {
  reason: string;
  action?: unknown;
}
export interface ManualResult {
  executed: ExecutedItem[];
  dropped: DroppedItem[];
}
export interface ChatResult extends ManualResult {
  line: string;
  error?: string | null;
}
export interface NetworkInfo {
  lan_ip: string;
  all_ips: string[];
  pair_url: string | null;
  public_url: string;
  relay_port: number;
  hint: string;
}
