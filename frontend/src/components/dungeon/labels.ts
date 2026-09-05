/**
 * 紫金地牢（dungeon_v2）前端显示名与工具函数。
 *
 * 中文为原文（与 zijin theme.json 的 bands/rooms/mark_stage_labels/ma_tier_labels/ending_labels 一致），
 * 英文由组件调用方经 useT() 查词典。后端 render 已下发 theme_labels（D11 E3），本表只作旧后端回退；
 * 有后端值优先（见下方 setThemeLabels/pick）。
 *
 * ⚠ 产品铁律：本文件与整个 dungeon/ 目录不得出现设备强度数字、通道、波形名。
 */
import type {
  DungeonAttr,
  DungeonBand,
  DungeonDice,
  DungeonEnding,
  DungeonMarkStage,
  DungeonMaTier,
  DungeonRoom,
  DungeonThemeLabels,
  DungeonUnmet,
} from "../../types";

/**
 * 后端 render.theme_labels（D11 E3）：有则优先，下面的本地表只作回退。
 * DungeonPanel 在每帧 render 到达时调用 setThemeLabels；换主题包 / 切 EN 时显示名自动跟随后端。
 */
let THEME: DungeonThemeLabels | null = null;
export function setThemeLabels(labels: DungeonThemeLabels | null | undefined): void {
  THEME = labels ?? null;
}
function pick(map: Record<string, string> | undefined, key: string): string | undefined {
  const v = map?.[key];
  return typeof v === "string" && v ? v : undefined;
}

export const BAND_ORDER: DungeonBand[] = ["entry", "mid", "upper", "lower", "end"];
export const BAND_LABEL: Record<DungeonBand, string> = {
  entry: "第零层 · 祭坛",
  mid: "浅层 · 一至二层",
  upper: "中层 · 三至五层",
  lower: "深层 · 六至九层",
  end: "结局",
};
/** 窄屏/剖面左栏用短名 */
export const BAND_SHORT: Record<DungeonBand, string> = {
  entry: "第零层",
  mid: "浅层",
  upper: "中层",
  lower: "深层",
  end: "结局",
};
export const BAND_TIER: Record<DungeonBand, string> = { entry: "Ⅰ", mid: "Ⅱ", upper: "Ⅲ", lower: "Ⅳ", end: "Ⅴ" };

export const ROOM_LABEL: Record<DungeonRoom, string> = {
  gate: "层门",
  corridor: "岔口",
  encounter: "遭遇",
  nest: "巢",
  rest: "安全区",
  treasure: "宝箱",
  trap: "陷阱",
  boss: "守护神",
  ending: "结局",
};

export const MARK_ORDER: DungeonMarkStage[] = ["none", "bud", "appear", "form", "set"];
export const MARK_LABEL: Record<DungeonMarkStage, string> = {
  none: "无",
  bud: "萌芽",
  appear: "显现",
  form: "成形",
  set: "定型",
};

export const MA_TIER_LABEL: Record<DungeonMaTier, string> = {
  human: "人",
  buffer: "缓冲",
  slow: "缓增",
  fast: "快增",
  instant: "完全魔化",
};
export const MA_TIER_DESC: Record<DungeonMaTier, string> = {
  human: "还是人",
  buffer: "缓冲：有点不像原来",
  slow: "缓增：慢慢变多",
  fast: "快增：藏不住",
  instant: "完全魔化",
};
/** 魔化档位阈值（constants.MO_HUA_*），HUD 刻度用 */
export const MA_TICKS = [100, 200, 300];

export const ENDING_LABEL: Record<DungeonEnding, string> = {
  escape: "破渊者",
  stay: "理智崩溃",
  sink: "欲海沉沦",
};

export const ATTR_LABEL: Record<DungeonAttr, string> = { str: "力量", dex: "敏捷", int: "智慧" };
export const ATTR_CODE: Record<DungeonAttr, string> = { str: "STR", dex: "DEX", int: "INT" };

export const DICE_NAME: Record<DungeonDice, string> = { d1: "D1", d4: "D4", d6: "D6", ed6: "永恒 D6" };
/** 骰子加成上限（constants.DICE_MAX_BONUS），选项可行性提示用 */
export const DICE_MAX_BONUS: Record<DungeonDice, number> = { d1: 1, d4: 4, d6: 6, ed6: 6 };

/** 结算类型 → 显示名（只在日志与「出口类」选项标签里用） */
export const SETTLEMENT_LABEL: Record<string, string> = {
  enter: "进入",
  move: "移动",
  take: "拿取",
  leave: "离开",
  rest: "休整",
  kill: "击退",
  yield: "屈从",
  defeat: "败北",
  escape: "逃脱",
  fall: "坠落",
  end_escape: "结局 · 逃",
  end_stay: "结局 · 留",
  end_sink: "结局 · 沉",
};
/** 选项上外露结算标签的集合（出口/休整类，帮玩家找路；其余不外露以免剧透） */
export const SETTLEMENT_SHOWN = new Set(["rest", "leave", "escape", "end_escape", "end_stay", "end_sink"]);

/** effects.applied 的 key → 显示名 */
export const EFFECT_LABEL: Record<string, string> = {
  yin_hua: "淫化",
  e_duo: "恶堕",
  ma: "魔化",
  hp: "HP",
  mp: "MP",
  str: "力量",
  dex: "敏捷",
  int: "智慧",
  stage_bud: "淫纹",
  stage_appear: "淫纹",
  stage_form: "淫纹",
  stage_set: "淫纹",
  stage_down: "淫纹",
  dice_gain: "骰子",
};

export function bandLabel(b: string): string {
  return pick(THEME?.bands, b) ?? (BAND_LABEL as Record<string, string>)[b] ?? b;
}
export function bandShort(b: string): string {
  return (BAND_SHORT as Record<string, string>)[b] ?? b;
}
export function bandTier(b: string): string {
  return (BAND_TIER as Record<string, string>)[b] ?? "";
}
export function roomLabel(r: string): string {
  return pick(THEME?.rooms, r) ?? (ROOM_LABEL as Record<string, string>)[r] ?? r;
}
export function markLabel(s: string): string {
  return pick(THEME?.mark_stage, s) ?? (MARK_LABEL as Record<string, string>)[s] ?? s;
}
export function markIndex(s: string): number {
  const i = MARK_ORDER.indexOf(s as DungeonMarkStage);
  return i < 0 ? 0 : i;
}
/** 短名：后端 ma_tier_labels 形如「缓冲：有点不像原来」，取冒号前；无则本地短名 */
export function maTierLabel(tier: string): string {
  const full = pick(THEME?.ma_tier, tier);
  if (full) return full.split(/[：:]/)[0];
  return (MA_TIER_LABEL as Record<string, string>)[tier] ?? tier;
}
export function maTierDesc(tier: string): string {
  return pick(THEME?.ma_tier, tier) ?? (MA_TIER_DESC as Record<string, string>)[tier] ?? tier;
}
export function endingLabel(e: string | null | undefined): string {
  if (!e) return "";
  return pick(THEME?.endings, e) ?? (ENDING_LABEL as Record<string, string>)[e] ?? e;
}
export function attrLabel(a: string): string {
  return (ATTR_LABEL as Record<string, string>)[a] ?? a;
}
export function attrCode(a: string): string {
  return (ATTR_CODE as Record<string, string>)[a] ?? a.toUpperCase();
}
export function diceName(d: string): string {
  return pick(THEME?.dice?.name, d) ?? (DICE_NAME as Record<string, string>)[d] ?? d.toUpperCase();
}
export function diceDesc(d: string): string {
  return pick(THEME?.dice?.desc, d) ?? "";
}
export function diceMaxBonus(d: string): number {
  return (DICE_MAX_BONUS as Record<string, number>)[d] ?? 0;
}
export function settlementLabel(s: string): string {
  return SETTLEMENT_LABEL[s] ?? s;
}
export function effectLabel(k: string): string {
  return EFFECT_LABEL[k] ?? k;
}

/** 检定可行性：稳过（属性已达 TN）/ 靠骰（属性 + 骰上限可达）/ 够不到 */
export type Feasibility = "sure" | "dice" | "none";
export function feasibility(attrValue: number, tn: number, dice: string): Feasibility {
  if (attrValue >= tn) return "sure";
  if (attrValue + diceMaxBonus(dice) >= tn) return "dice";
  return "none";
}

type Tr = (zh: string, vars?: Record<string, string | number>) => string;
/**
 * 结构化门槛 → 文案（D11 E2，替代旧的 prettifyReason 正则）。tr = useT() 返回的翻译函数。
 * stage_min → 「淫纹需至少 显现（当前 无）」；*_gte → 「魔化 需 ≥ 100（当前 20）」；未知键回后端 text。
 */
export function unmetText(u: DungeonUnmet, tr: Tr): string {
  if (u.key === "stage_min") {
    return tr("淫纹需至少 {need}（当前 {cur}）", {
      need: tr(markLabel(String(u.need))),
      cur: tr(markLabel(String(u.current ?? "none"))),
    });
  }
  if (u.key.endsWith("_gte")) {
    const field = u.key.slice(0, -4);
    return tr("{what} 需 ≥ {need}（当前 {cur}）", {
      what: tr(effectLabel(field)),
      need: String(u.need),
      cur: String(u.current ?? "?"),
    });
  }
  return u.text || u.key;
}

/** 后端错误码 → 面板提示（错误串形如「[code] 中文说明」）。 */
export type DungeonErrorKind = "estop" | "old_save" | "no_save" | "run_over" | "no_run" | "generic";
export function classifyError(msg: string): { kind: DungeonErrorKind; code: string; text: string } {
  const m = /^\[([a-z_]+)\]\s*([\s\S]*)$/.exec(msg.trim());
  const code = m ? m[1] : "";
  const rest = m ? m[2].trim() : msg;
  switch (code) {
    case "estop":
      return { kind: "estop", code, text: "急停中：设备已清零，地牢暂停推进。解除急停后再继续。" };
    case "save_format":
    case "save_version":
    case "save_corrupt":
      return { kind: "old_save", code, text: "旧版存档不兼容，请新开" };
    case "save_missing":
      return { kind: "no_save", code, text: "没有可读取的存档" };
    case "run_ended":
    case "run_locked":
      return { kind: "run_over", code, text: "本局已结束，请新开一局" };
    case "no_run":
      return { kind: "no_run", code, text: "没有进行中的地牢局" };
    case "require_unmet":
      return { kind: "generic", code, text: rest || msg };
    // D30 路网选路
    case "not_reachable":
      return { kind: "generic", code, text: "那里现在去不了" };
    case "not_awaiting":
      return { kind: "generic", code, text: "先把眼前的事走完，再选路" };
    case "not_map":
      return { kind: "generic", code, text: "当前不是路网模式" };
    case "bad_node":
      return { kind: "generic", code, text: "没有选中要去的地方" };
    default:
      return { kind: "generic", code, text: rest || msg };
  }
}

/** 路网节点态 → 显示名（aria / tooltip 用） */
export const ROUTE_STATE_LABEL: Record<string, string> = {
  current: "当前",
  reachable: "可达",
  gated: "受阻",
  visited: "已过",
  bypassed: "已弃",
  locked: "未达",
  fog: "未知",
};
export function routeStateLabel(s: string): string {
  return ROUTE_STATE_LABEL[s] ?? s;
}
/** gated 节点原因文案：gate.unmet[] → 「；」拼接（走 unmetText 词典） */
export function gateText(gate: { unmet: DungeonUnmet[] } | undefined, tr: Tr): string {
  const list = gate?.unmet ?? [];
  return list.map((u) => unmetText(u, tr)).join("；");
}
