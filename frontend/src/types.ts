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
  lang: string;
  en_available: boolean;
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

// ---------- 地牢（紫金地牢 · dungeon_v2） ----------
// 权威契约：backend/dungeon_v2/render.py（字段只加不删）。run 为 run.snapshot()：RunState 拍平 + 进度字段，无嵌套子对象。
export type DungeonBand = "entry" | "mid" | "upper" | "lower" | "end";
export type DungeonRoom =
  | "gate" | "corridor" | "encounter" | "nest" | "rest" | "treasure" | "trap" | "boss" | "ending";
export type DungeonMarkStage = "none" | "bud" | "appear" | "form" | "set";
export type DungeonDice = "d1" | "d4" | "d6" | "ed6";
export type DungeonMaTier = "human" | "buffer" | "slow" | "fast" | "instant";
export type DungeonPhase = "playing" | "ended" | "locked";
export type DungeonEnding = "escape" | "stay" | "sink";
export type DungeonAttr = "str" | "dex" | "int";

export interface DungeonPack {
  id: string;
  title: string;
  description?: string;
  themes: string[];
  event_count: number;
  version?: string;
  engine?: string;
}
/** run.snapshot()：RunState.to_dict() + 进度字段（拍平）。 */
export interface DungeonRun {
  // RunState
  yin_hua: number;
  e_duo: number;
  ma: number;
  ma_cap: number;
  str: number;
  dex: number;
  int: number;
  hp: number;
  mp: number;
  mark_stage: DungeonMarkStage | string;
  crossed_gate: boolean;
  defected: boolean;
  dice: DungeonDice | string;
  dice_name: string;
  dice_desc: string;
  ma_tier: DungeonMaTier | string;
  ability: unknown[];
  flags: Record<string, string>;
  // 进度
  seed: number;
  pack_id: string;
  event_id: string;
  visit_n: number;
  turn: number;
  phase: DungeonPhase | string;
  ending: DungeonEnding | string | null;
  defeats: number;
  visits: Record<string, number>;
  log: DungeonLogEntry[];
  engine?: string;
}
/** checks.resolve_check 记录（outcome.check / log[].check）。 */
export interface DungeonCheckRecord {
  attr: DungeonAttr | string;
  tn: number;
  attr_value: number;
  dice: DungeonDice | string;
  raw: number;
  zeroed: boolean;
  bonus: number;
  total: number;
  success: boolean;
}
export interface DungeonEffectApplied {
  key: string;
  value: number | boolean | string;
  before: number | string;
  after: number | string;
}
export interface DungeonEffectSkipped {
  key: string;
  value: unknown;
  reason: string;
}
export interface DungeonGateCheck {
  stage: string;
  ma: number;
  crossed: boolean;
}
/** run.log 条目：start / enter / advance 三种（engine._log）。 */
export interface DungeonLogEntry {
  turn: number;
  type: "start" | "enter" | "advance" | string;
  // start
  seed?: number;
  str?: number;
  dex?: number;
  int?: number;
  // enter / advance
  event?: string;
  visit_n?: number;
  variant?: number;
  feedback?: string[];
  // advance
  choice?: number;
  label?: string;
  check?: DungeonCheckRecord | null;
  folded_to?: number | null;
  folded_label?: string | null;
  settlement?: string;
  effects?: DungeonEffectApplied[];
  skipped?: DungeonEffectSkipped[];
  dice_gain?: string | null;
  defeat?: boolean;
  gate_check?: DungeonGateCheck;
  ending?: string;
}
export interface DungeonChoiceCheck {
  attr: DungeonAttr | string;
  tn: number;
  attr_value: number;
  dice: DungeonDice | string;
}
/** 结构化未满足门槛（D11 E2）：key = require 键（stage_min / ma_gte …），need = 门槛值，current = 当前值，text = 后端中文兜底。 */
export interface DungeonUnmet {
  key: string;
  need: string | number;
  current: string | number | null;
  text: string;
}
export interface DungeonChoice {
  id: string;
  label: string;
  settlement: string;
  disabled: boolean;
  disabled_reason?: string;
  unmet?: DungeonUnmet[];
  check?: DungeonChoiceCheck;
  require?: Record<string, string | number>;
  estop_overrides?: boolean;
}
export interface DungeonEvent {
  id: string;
  title: string;
  theme_id: string;
  kind: string;
  content_level: number;
  tier: number;
  choices: DungeonChoice[];
  free_input: boolean;
  band: DungeonBand | string;
  room: DungeonRoom | string;
  intensity: string;
  species: string;
  settlement: string[];
  checks: unknown[];
  visit_n: number;
  variant: { index: number; count: number };
  feedback_raw: string;
}
export interface DungeonFeedback {
  hint: string;
  cores: string[];
  label: string;
}
/** 设备动作回执。⚠ label / reason 含设备描述，地牢 UI 只许统计条数，禁止渲染其文本（产品铁律）。 */
export interface DungeonExecuted {
  action: Record<string, unknown>;
  reason: string;
  sent: boolean;
  label: string;
}
export interface DungeonDropped {
  action: Record<string, unknown>;
  reason: string;
}
export interface DungeonOutcome {
  event: string;
  choice: number;
  label: string;
  effective_choice: number;
  effective_label: string;
  settlement: string;
  check: DungeonCheckRecord | null;
  folded: boolean;
  effects: DungeonEffectApplied[];
  skipped: DungeonEffectSkipped[];
  dice_gain: string | null;
  defeat: boolean;
  gate_checked: boolean;
  crossed: boolean;
  ending: DungeonEnding | string | null;
  next_event: string | null;
  exit: string;
  estop_overrides: boolean;
}
/** chain 剖面节点（render.map_view chain 分支） */
export interface DungeonMapNode {
  id: string;
  title: string;
  band: DungeonBand | string;
  room: DungeonRoom | string;
  visited: number;
  current: boolean;
}
export interface DungeonChainMap {
  mode: "chain";
  current: string;
  nodes: DungeonMapNode[];
}
/** 路网节点态（D26 §2.1 / D25 map_logic.NODE_STATES；fog 为 revealed=false 的前端表现，引擎当前不发） */
export type DungeonRouteNodeState = "current" | "reachable" | "gated" | "visited" | "bypassed" | "locked" | "fog";
export interface DungeonRouteNode {
  id: string;
  floor: number;
  col: number;
  room: DungeonRoom | string;
  band: DungeonBand | string;
  state: DungeonRouteNodeState | string;
  revealed: boolean;
  /** 仅 visited / current 下发 */
  title?: string;
  /** 仅 gated 下发：D11 结构化门槛 */
  gate?: { unmet: DungeonUnmet[] };
}
export interface DungeonRouteEdge {
  from: string;
  to: string;
}
export interface DungeonRouteEnding {
  kind: DungeonEnding | string;
  reached: boolean;
}
/** 深渊路网（D26 §6.1 契约，D25 render_map 下发） */
export interface DungeonRouteMap {
  mode: "map";
  floors: number;
  current: string;
  awaiting_move: boolean;
  nodes: DungeonRouteNode[];
  edges: DungeonRouteEdge[];
  path: string[];
  terminus: { boss: string; endings: DungeonRouteEnding[] };
  seed_label: string;
}
export type DungeonMap = DungeonChainMap | DungeonRouteMap;
export function isRouteMap(m: DungeonMap | null | undefined): m is DungeonRouteMap {
  return !!m && m.mode === "map" && Array.isArray((m as DungeonRouteMap).edges);
}
/** 主题显示名（D11 E3）：来自包 theme.json + constants 骰子表（按 lang 切）。前端优先读，本地表回退。 */
export interface DungeonThemeLabels {
  bands: Record<string, string>;
  rooms: Record<string, string>;
  mark_stage: Record<string, string>;
  ma_tier: Record<string, string>;
  feedback: Record<string, string>;
  endings?: Record<string, string>;
  dice: { name: Record<string, string>; desc: Record<string, string> };
}
export interface DungeonRender {
  run: DungeonRun;
  event: DungeonEvent;
  narrative: { text: string; source: string } | null;
  feedback: DungeonFeedback;
  executed: DungeonExecuted[];
  dropped: DungeonDropped[];
  map: DungeonMap;
  outcome: DungeonOutcome | null;
  theme_labels?: DungeonThemeLabels;
}
export interface DungeonState {
  active: boolean;
  packs: DungeonPack[];
  run: DungeonRun | null;
  engine?: string;
  pack_errors?: Record<string, string>;
  estop?: boolean;
  last_event?: DungeonEvent | null;
}
