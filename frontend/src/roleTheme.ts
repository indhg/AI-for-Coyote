// 角色/强度档的 UI 主题映射
// Tailwind v4 必须用完整字面类名（运行时拼接不会被打包）
import avatarCushou from "./assets/theme-cushou.png";
import avatarPingpinghui from "./assets/theme-pingpinghui.png";
import avatarGebulin from "./assets/theme-gebulin.png";
import avatarShilaimu from "./assets/theme-shilaimu.png";
import avatarZhuhou from "./assets/theme-zhuhou.png";

// ---------- 角色入口表（收敛后的 UI 模型） ----------
// 角色不再按「纯爱/调教/凌辱」风格分档展示，每个入口 = 一个角色 + 它的正式内容档。
// 体验版 = 触手·纯爱（入门试玩），入口常驻、带「新手推荐」角标（点过一次后角标消失）。
// 触手/品评会正式内容 = 调教+凌辱融合稿；哥布林/史莱姆/蛛后 = 各自凌辱稿。
// 后端 character.yaml 每角色只挂一个「正式」档（配置已收敛）；UI 入口表与之对齐。
// 以后做内容取舍时改这里的 profile 指向 / character.yaml 的 prompt_file 即可。
export interface Entry {
  key: string;       // 唯一键
  label: string;     // UI 显示名（角色就叫名字，不做风格区分）
  role: string;      // 后端角色名（config roles 键）
  profile: string;   // 该入口使用的正式内容档
  trial?: boolean;   // 体验版（新手推荐角标，点过一次后消失）
  recommended?: boolean; // 常驻「推荐」标记（内容最成熟/最值得先玩的正式角色）
}

export const ENTRIES: Entry[] = [
  { key: "trial", label: "体验版", role: "体验版", profile: "正式", trial: true },
  { key: "cushou", label: "触手", role: "触手", profile: "正式", recommended: true },
  { key: "appraisal", label: "品评会", role: "品评会", profile: "正式", recommended: true },
  { key: "goblin", label: "哥布林", role: "哥布林", profile: "正式" },
  { key: "slime", label: "史莱姆", role: "史莱姆", profile: "正式" },
  { key: "zhuhou", label: "蛛后", role: "蛛后", profile: "正式" },
];

/** 按当前 (role, profile) 反查入口；匹配不到返回 null（如后端临时处于素材档） */
export function entryOf(role: string, profile: string): Entry | null {
  return (
    ENTRIES.find((e) => e.role === role && e.profile === profile) ??
    ENTRIES.find((e) => e.role === role) ?? // 同角色任意档也算命中该入口
    null
  );
}

export const ENTRY_AVATARS: Record<string, string> = {
  trial: avatarCushou, // 体验版 = 触手·纯爱，用同一张触手头像
  cushou: avatarCushou,
  appraisal: avatarPingpinghui,
  goblin: avatarGebulin,
  slime: avatarShilaimu,
  zhuhou: avatarZhuhou,
};

export function entryAvatar(key: string): string | null {
  return ENTRY_AVATARS[key] ?? null;
}

// 入口标识色（用于卡片描边 / 列表点亮）—— 2026-09-05 用户拍板：非 active 透明、只 active 亮色（避免 violet 常态发亮）；现为空 map，hover/active 亮色由 ENTRY_RING_ACTIVE_CLS 提供
export const ENTRY_RING_CLS: Record<string, string> = {
};

export const ENTRY_RING_ACTIVE_CLS: Record<string, string> = {
  trial: "border-violet-400 bg-violet-500/15",
  cushou: "border-violet-400 bg-violet-500/15",
  appraisal: "border-rose-400 bg-rose-500/15",
  goblin: "border-green-400 bg-green-500/15",
  slime: "border-cyan-400 bg-cyan-500/15",
  zhuhou: "border-purple-400 bg-purple-500/15",
};

// ---------- 强度档（电击强度，与对话内容无关） ----------
// 只作用于最终电击强度：轻=×0.7 / 中=×1.0 / 重=×1.3；重启回默认「中」
export const INTENSITY_LEVELS = ["轻", "中", "重"] as const;
export type IntensityLevel = (typeof INTENSITY_LEVELS)[number];

export const INTENSITY_BADGE_CLS: Record<string, string> = {
  轻: "border-emerald-500/60 bg-emerald-500/15 text-emerald-300",
  中: "border-line2 bg-accent/15 text-accent",
  重: "border-red-500/60 bg-red-500/15 text-red-300",
};

export const INTENSITY_DOT_CLS: Record<string, string> = {
  轻: "bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.5)]",
  中: "bg-accent shadow-[0_0_8px_var(--color-accent)]",
  重: "bg-red-400 shadow-[0_0_8px_rgba(248,113,113,0.5)]",
};
