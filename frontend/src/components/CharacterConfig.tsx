import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { useApp } from "../store";
import { useT } from "../i18n";

// 侧边栏底部：称谓设置 + 内容/语言包安装（zh/en 大包）
export default function CharacterConfig() {
  const t = useT();
  const nick = useApp((st) => st.state?.config_info?.player_nick ?? "小柳");
  const [draft, setDraft] = useState(nick);
  useEffect(() => setDraft(nick), [nick]);
  // EN 模式：默认昵称「小柳」仅显示为 Liu，改动仍是用户自己的文本
  const showNick = nick === "小柳" ? t("小柳") : nick;

  const fileRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

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

  const onPick = async (file: File | null) => {
    if (!file || busy) return;
    setBusy(true);
    setMsg(null);
    setErr(null);
    try {
      const r = await api.installContent(file);
      setMsg(
        t("已安装 {n} 个文件（新增 {a} / 更新 {u}），角色与地牢内容已刷新", {
          n: String(r.files),
          a: String(r.added),
          u: String(r.updated),
        }),
      );
      setTimeout(() => window.location.reload(), 1200);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mt-3 space-y-3">
      <div className="rounded-[14px] border border-line bg-panel p-3.5">
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

      <div className="rounded-[14px] border border-line bg-panel p-3.5">
        <div className="mb-1.5 text-[12px] font-semibold tracking-[1.5px] text-muted">{t("内容 / 语言包")}</div>
        <div className="mb-2 text-[11px] leading-relaxed text-faint">
          {t("安装 DLC 的 zh / en 内容包 zip，自动合并进 content/ 并即时生效。")}
        </div>
        <button
          onClick={() => fileRef.current?.click()}
          disabled={busy}
          className="w-full rounded-[8px] border border-accent/40 bg-accent/10 px-2 py-1.5 text-[12px] font-medium text-accent transition-colors hover:bg-accent/20 disabled:opacity-50"
        >
          {busy ? t("安装中…") : t("选择 zip 并安装")}
        </button>
        <input
          ref={fileRef}
          type="file"
          accept=".zip"
          className="hidden"
          onChange={(e) => {
            void onPick(e.target.files?.[0] ?? null);
            e.target.value = "";
          }}
        />
        {msg && <div className="mt-2 text-[11px] leading-relaxed text-ok">{msg}</div>}
        {err && <div className="mt-2 break-all text-[11px] leading-relaxed text-warn">{err}</div>}
      </div>
    </div>
  );
}
