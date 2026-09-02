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
  user_caps: Record<"A" | "B", number>;
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
  intensity_level: string;
  strength_scale: Record<"A" | "B", number>;
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
  test_mode: boolean;
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
  update: {
    enabled: boolean;
    latest: string;
    url: string;
    available: boolean;
  };
  character: string;
  dungeon: DungeonState;
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

// ---------- 地牢（紫金地牢） ----------
export interface DungeonPack {
  id: string;
  title: string;
  themes: string[];
  event_count: number;
}
export interface DungeonRunState {
  hp: number;
  will: number;
  affinity: Record<string, number>;
  heat?: number;
  orgasm_count?: number;
}
export interface DungeonRun {
  preset_id: string;
  active_themes: string[];
  mix_policy: string;
  seed: number;
  floors: number;
  floor_index: number;
  room_index: number;
  event_id: string | null;
  turn_index: number;
  run_state: DungeonRunState;
  flags: Record<string, unknown>;
  visited: string[];
  phase: string;
  ending_id: string | null;
}
export interface DungeonChoice {
  id: string;
  label: string;
}
export interface DungeonEvent {
  id: string;
  title: string;
  theme_id: string;
  kind: string;
  content_level: string;
  tier: number;
  choices: DungeonChoice[];
  free_input: boolean;
}
export interface DungeonRender {
  run: DungeonRun;
  event: DungeonEvent | null;
  narrative: { text: string; source: string } | null;
  feedback: { hint: string };
  executed: string[];
  dropped: string[];
  map?: DungeonMap;
}
export interface DungeonMapNode {
  row: number;
  col: number;
}
export interface DungeonMap {
  floor: number;
  rows: number;
  cols: number;
  node_types: Record<string, string>;
  node_elite: Record<string, boolean>;
  boss: { row: number; col: number };
  edges: { from: DungeonMapNode; to: DungeonMapNode }[];
  entry: DungeonMapNode[];
  visited_nodes: string[];
  chains: Record<string, string>;
  current: (DungeonMapNode & { floor?: number; boss?: boolean }) | null;
  reachable: DungeonMapNode[];
  phase: string;
}
export interface DungeonState {
  active: boolean;
  packs: DungeonPack[];
  run?: DungeonRun;
}
