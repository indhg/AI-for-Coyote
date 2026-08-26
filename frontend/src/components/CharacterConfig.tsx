import { useEffect, useState } from "react";
import { api } from "../api";
import { useApp } from "../store";

const STYLE_LABELS: Record<string, string> = {
  调教: "调教版",
  纯爱: "纯爱版",
};

// zustand selector 必须返回稳定引用，不能内联新数组（否则无限重渲染）
const DEFAULT_PROFILES: string[] = ["调教", "纯爱"];

export default function CharacterConfig() {
  const profile = useApp((st) => st.state?.profile ?? "调教");
  const profiles = useApp((st) => st.state?.profiles ?? DEFAULT_PROFILES);
  const nick = useApp((st) => st.state?.config_info?.player_nick ?? "小柳");
  const [draft, setDraft] = useState(nick);
  useEffect(() => setDraft(nick), [nick]);

  const switchProfile = async (p: string) => {
    if (p === profile) return;
    try {
      await api.setProfile(p);
    } catch {
      /* 状态由 ws 推送刷新 */
    }
  };

  const saveNick = async () => {
    const v = draft.trim();
    if (!v || v === nick) {
      setDraft(nick);
      return;
    }
    try {
      await api.setNick(v);
    } catch {
      /* 状态由 ws 推送刷新 */
    }
  };

  return (
    <div className="mt-3 rounded-[14px] border border-line bg-panel p-3.5">
      <div className="mb-2 text-[12px] font-semibold tracking-[1.5px] text-muted">角色设置</div>

      <div className="mb-2 text-[11px] text-muted">对话风格</div>
      <div className="flex gap-1.5">
        {profiles.map((p) => (
          <button
            key={p}
            onClick={() => void switchProfile(p)}
            className={`flex-1 rounded-[8px] border px-2 py-1.5 text-[12px] transition-colors ${
              p === profile
                ? "border-accent bg-accent font-semibold text-ink"
                : "border-line bg-panel2 text-muted hover:border-line2"
            }`}
          >
            {STYLE_LABELS[p] ?? p}
          </button>
        ))}
      </div>
      <p className="mt-1 text-[10px] text-faint">
        {profile === "纯爱" ? "温柔驯服·依赖顺从" : "黑暗调教·支配胁迫"}
      </p>

      <div className="mb-2 mt-3 text-[11px] text-muted">称谓（AI 怎么叫你）</div>
      <input
        value={draft}
        maxLength={20}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={() => void saveNick()}
        onKeyDown={(e) => {
          if (e.key === "Enter") (e.target as HTMLInputElement).blur();
        }}
        placeholder="小柳"
        className="w-full rounded-[8px] border border-line bg-panel2 px-2 py-1.5 text-[13px] outline-none"
      />
    </div>
  );
}
