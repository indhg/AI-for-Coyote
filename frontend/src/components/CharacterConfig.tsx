import { useEffect, useState } from "react";
import { api } from "../api";
import { useApp } from "../store";
import { useT } from "../i18n";

// 侧边栏底部的称谓设置（角色/风格档切换已上移到顶部 RoleCard）
export default function CharacterConfig() {
  const t = useT();
  const nick = useApp((st) => st.state?.config_info?.player_nick ?? "小柳");
  const [draft, setDraft] = useState(nick);
  useEffect(() => setDraft(nick), [nick]);
  // EN 模式：默认昵称「小柳」仅显示为 Liu，改动仍是用户自己的文本
  const showNick = nick === "小柳" ? t("小柳") : nick;

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
      <div className="mb-2 text-[12px] font-semibold tracking-[1.5px] text-muted">{t("称谓（AI 怎么叫你）")}</div>
      <input
        value={draft === "小柳" ? t("小柳") : draft}
        maxLength={20}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={() => void saveNick()}
        onKeyDown={(e) => {
          if (e.key === "Enter") (e.target as HTMLInputElement).blur();
        }}
        placeholder={t("小柳")}
        className="w-full rounded-[8px] border border-line bg-panel2 px-2 py-1.5 text-[13px] outline-none"
      />
    </div>
  );
}
