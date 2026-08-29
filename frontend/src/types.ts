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
export interface RoleProfile {
  name: string;
  level: string;
  note: string;
  available: boolean;
}
export interface RoleInfo {
  name: string;
  label: string;
  title: string;
  device_narrative: string;
  profiles: RoleProfile[];
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
  baseline_strength: Record<"A" | "B", number>;
  patterns: Record<"A" | "B", string | null>;
  role: string;
  role_title: string;
  roles: RoleInfo[];
  profile: string;
  profiles: string[];
  profile_available: Record<string, boolean>;
  profile_level: string;
  autopilot: boolean;
  autopilot_interval_s: number;
  sensors_on: boolean;
  sensors: { camera: boolean; audio: boolean };
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
  camera: {
    enabled: boolean;
    has_frame: boolean;
    last_ts: number;
    interval_s: number;
    mean_brightness: number;
    dark: boolean;
    dark_threshold: number;
    error: string;
  };
  audio: {
    enabled: boolean;
    running: boolean;
    last_text: string;
    last_ts: number;
    level: number;
    level_pct?: number;
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
    version: string;
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
