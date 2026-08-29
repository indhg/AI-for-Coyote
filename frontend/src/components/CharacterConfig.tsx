import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { useApp } from "../store";

const STYLE_LABELS: Record<string, string> = {
  纯爱: "纯爱版",
  调教: "调教版",
};

// zustand selector 必须返回稳定引用，不能内联新数组（否则无限重渲染）
const DEFAULT_PROFILES: string[] = ["纯爱", "调教"];

export default function CharacterConfig() {
  const profile = useApp((st) => st.state?.profile ?? "纯爱");
  const profiles = useApp((st) => st.state?.profiles ?? DEFAULT_PROFILES);
  const avail = useApp((st) => st.state?.profile_available);
  const nick = useApp((st) => st.state?.config_info?.player_nick ?? "小柳");
  const [draft, setDraft] = useState(nick);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [importing, setImporting] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  useEffect(() => setDraft(nick), [nick]);

  const switchProfile = async (p: string) => {
    if (p === profile) return;
    setErr("");
    try {
      await api.setProfile(p);
    } catch (e) {
      setErr(
        `「${STYLE_LABELS[p] ?? p}」未安装：点下方「导入 DLC」选择 .zip 或 .md 即可，导入后自动生效。${(e as Error).message ? `（${(e as Error).message}）` : ""}`,
      );
    }
  };

  const importDlc = async (f: File) => {
    setImporting(true);
    setErr("");
    setMsg("");
    try {
      const r = await api.importDlc(f);
      setMsg(`已导入 ${r.files?.length ?? 0} 个文件到 content\\pack\\${r.dir}${r.profile ? "，已自动启用「" + r.profile + "」" : ""}`);
      if (r.profile && r.profile !== profile) {
        await api.setProfile(r.profile).catch(() => undefined);
      }
    } catch (e) {
      setErr(`导入失败：${(e as Error).message}`);
    } finally {
      setImporting(false);
      if (fileRef.current) fileRef.current.value = "";
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
        {profiles.map((p) => {
          const ok = avail?.[p] ?? true;
          return (
            <button
              key={p}
              disabled={!ok}
              title={ok ? undefined : `${STYLE_LABELS[p] ?? p}需要安装对应 DLC（content\\pack\\）`}
              onClick={() => void switchProfile(p)}
              className={`flex-1 rounded-[8px] border px-2 py-1.5 text-[12px] transition-colors ${
                p === profile
                  ? "border-accent bg-accent font-semibold text-ink"
                  : ok
                    ? "border-line bg-panel2 text-muted hover:border-line2"
                    : "cursor-not-allowed border-line bg-panel2 text-faint opacity-60"
              }`}
            >
              {STYLE_LABELS[p] ?? p}
              {!ok && <span className="ml-1 text-[10px]">未装DLC</span>}
            </button>
          );
        })}
      </div>
      <p className="mt-1 text-[10px] text-faint">
        {profile === "纯爱" ? "温柔驯服·依赖顺从" : "黑暗调教·支配胁迫（DLC1）"}
      </p>
      {err && <p className="mt-1.5 text-[10px] leading-relaxed text-red-400">{err}</p>}
      {msg && <p className="mt-1.5 text-[10px] leading-relaxed text-emerald-400">{msg}</p>}

      <input
        ref={fileRef}
        type="file"
        accept=".zip,.md"
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) void importDlc(f);
        }}
      />
      <button
        disabled={importing}
        onClick={() => fileRef.current?.click()}
        className="mt-2 w-full rounded-[8px] border border-dashed border-line px-2 py-1.5 text-[12px] text-muted transition-colors hover:border-line2 disabled:opacity-60"
      >
        {importing ? "导入中…" : "导入 DLC（选择 .zip 或 .md，自动装进 content\\pack）"}
      </button>

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
