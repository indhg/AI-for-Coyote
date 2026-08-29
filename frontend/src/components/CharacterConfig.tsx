import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { useApp } from "../store";
import type { RoleInfo } from "../types";

const STYLE_LABELS: Record<string, string> = {
  纯爱: "纯爱版",
  调教: "调教版",
};

const LEVEL_BADGE: Record<string, string> = {
  轻: "轻",
  中: "中",
  重: "重",
};

// zustand selector 必须返回稳定引用，不能内联新数组（否则无限重渲染）
const DEFAULT_ROLES: RoleInfo[] = [];

export default function CharacterConfig() {
  const role = useApp((st) => st.state?.role ?? "触手");
  const roles = useApp((st) => st.state?.roles ?? DEFAULT_ROLES);
  const profile = useApp((st) => st.state?.profile ?? "纯爱");
  const nick = useApp((st) => st.state?.config_info?.player_nick ?? "小柳");
  const [draft, setDraft] = useState(nick);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [importing, setImporting] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  useEffect(() => setDraft(nick), [nick]);

  const currentRole =
    roles.find((r) => r.name === role) ?? {
      name: role,
      label: role,
      title: "主人",
      device_narrative: "触手",
      profiles: [],
    };
  const roleProfiles = currentRole.profiles ?? [];

  const switchRole = async (r: string) => {
    if (r === role) return;
    setErr("");
    const rInfo = roles.find((x) => x.name === r);
    const first = rInfo?.profiles?.find((p) => p.available) ?? rInfo?.profiles?.[0];
    if (!first) {
      setErr(`「${rInfo?.label ?? r}」未安装：先点下方「导入 DLC」安装内容包。`);
      return;
    }
    try {
      await api.setProfile(r, first.name);
    } catch (e) {
      setErr(`切换失败：${(e as Error).message}`);
    }
  };

  const switchProfile = async (p: string) => {
    if (p === profile) return;
    setErr("");
    try {
      await api.setProfile(role, p);
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
      setMsg(
        `已导入 ${r.files?.length ?? 0} 个文件到 content\\pack\\${r.dir}${r.profile ? "，已自动启用「" + r.profile + "」" : ""}`,
      );
      if (r.profile && r.profile !== profile) {
        await api.setProfile(role, r.profile).catch(() => undefined);
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

      <div className="mb-2 text-[11px] text-muted">角色</div>
      <div className="flex gap-1.5">
        {roles.map((r) => {
          const usable = (r.profiles ?? []).some((p) => p.available);
          return (
            <button
              key={r.name}
              disabled={!usable}
              title={usable ? undefined : `${r.label}需要安装对应 DLC（content\\pack\\）`}
              onClick={() => void switchRole(r.name)}
              className={`flex-1 rounded-[8px] border px-2 py-1.5 text-[12px] transition-colors ${
                r.name === role
                  ? "border-accent bg-accent font-semibold text-ink"
                  : usable
                    ? "border-line bg-panel2 text-muted hover:border-line2"
                    : "cursor-not-allowed border-line bg-panel2 text-faint opacity-60"
              }`}
            >
              {r.label}
              {!usable && <span className="ml-1 text-[10px]">未装</span>}
            </button>
          );
        })}
      </div>

      <div className="mb-2 mt-3 text-[11px] text-muted">风格档</div>
      <div className="flex gap-1.5">
        {roleProfiles.map((p) => {
          const ok = p.available;
          return (
            <button
              key={p.name}
              disabled={!ok}
              title={ok ? undefined : `${STYLE_LABELS[p.name] ?? p.name}需要安装对应 DLC（content\\pack\\）`}
              onClick={() => void switchProfile(p.name)}
              className={`flex-1 rounded-[8px] border px-2 py-1.5 text-[12px] transition-colors ${
                p.name === profile
                  ? "border-accent bg-accent font-semibold text-ink"
                  : ok
                    ? "border-line bg-panel2 text-muted hover:border-line2"
                    : "cursor-not-allowed border-line bg-panel2 text-faint opacity-60"
              }`}
            >
              {STYLE_LABELS[p.name] ?? p.name}
              {LEVEL_BADGE[p.level] && (
                <span className="ml-1 text-[10px] opacity-80">{LEVEL_BADGE[p.level]}</span>
              )}
              {!ok && <span className="ml-1 text-[10px]">未装DLC</span>}
            </button>
          );
        })}
      </div>
      <p className="mt-1 text-[10px] text-faint">
        {profile === "纯爱" && role === "触手"
          ? "温柔驯服·依赖顺从"
          : profile === "调教" && role === "触手"
            ? "黑暗调教·支配胁迫（DLC1）"
            : role === "品评会"
              ? "公开审评·装置支配（DLC2，重口）"
              : ""}
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
