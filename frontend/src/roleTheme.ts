// 角色/风格档的 UI 主题映射：档位轻/中/重 = 绿/金/红；角色标识色用于卡片描边
// Tailwind v4 必须用完整字面类名（运行时拼接不会被打包）
import avatarCushou from "./assets/theme-cushou.png";
import avatarPingpinghui from "./assets/theme-pingpinghui.png";

// 主题头像（像素风，随包分发）；未配置的主题回退首字块
export const ROLE_AVATARS: Record<string, string> = {
  触手: avatarCushou,
  品评会: avatarPingpinghui,
};

export function roleAvatar(role: string): string | null {
  return ROLE_AVATARS[role] ?? null;
}
export const LEVEL_BADGE_CLS: Record<string, string> = {
  轻: "border-emerald-500/60 bg-emerald-500/15 text-emerald-300",
  中: "border-line2 bg-accent/15 text-accent",
  重: "border-red-500/60 bg-red-500/15 text-red-300",
};

// 档位显示名（用户定名）：轻→纯爱、中→调教、重→凌辱
export const LEVEL_LABELS: Record<string, string> = {
  轻: "纯爱",
  中: "调教",
  重: "凌辱",
};

export const LEVEL_DOT_CLS: Record<string, string> = {
  轻: "bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.5)]",
  中: "bg-accent shadow-[0_0_8px_var(--color-accent)]",
  重: "bg-red-400 shadow-[0_0_8px_rgba(248,113,113,0.5)]",
};

export const ROLE_RING_CLS: Record<string, string> = {
  触手: "border-violet-500/60",
  品评会: "border-rose-500/60",
};

export const ROLE_RING_ACTIVE_CLS: Record<string, string> = {
  触手: "border-violet-400 bg-violet-500/15",
  品评会: "border-rose-400 bg-rose-500/15",
};

export const STYLE_LABELS: Record<string, string> = {
  纯爱: "纯爱版",
  调教: "调教版",
};

export const STYLE_DESCS: Record<string, string> = {
  "触手·纯爱": "温柔驯服·依赖顺从",
  "触手·调教": "黑暗调教·支配胁迫（DLC1）",
  "品评会·调教": "公开审评·装置支配（DLC2）",
};

export function styleDesc(role: string, profile: string): string {
  return STYLE_DESCS[`${role}·${profile}`] ?? "";
}
