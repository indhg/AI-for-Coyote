import { useEffect, useRef, useState } from "react";
import { Check, ChevronDown, ChevronUp } from "lucide-react";
import { api } from "../api";
import { useApp } from "../store";
import type { RoleInfo } from "../types";
import {
  LEVEL_BADGE_CLS,
  LEVEL_DOT_CLS,
  LEVEL_LABELS,
  ROLE_RING_ACTIVE_CLS,
  ROLE_RING_CLS,
  STYLE_LABELS,
  styleDesc,
} from "../roleTheme";

// zustand selector 必须返回稳定引用，不能内联新数组（否则无限重渲染）
const EMPTY_ROLES: RoleInfo[] = [];
// 固定三档：轻 / 中 / 凌辱（重），按角色支持情况点亮
const LEVELS = ["轻", "中", "重"];

// 侧边栏顶部的「当前角色卡」：只显示当前角色一行；点开浮动小下拉——上段选角色列表，下段固定三档（支持的才亮）
export default function RoleCard() {
  const role = useApp((st) => st.state?.role ?? "触手");
  const roles = useApp((st) => st.state?.roles ?? EMPTY_ROLES);
  const profile = useApp((st) => st.state?.profile ?? "纯爱");
  const [open, setOpen] = useState(false);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const rootRef = useRef<HTMLDivElement>(null);

  const current = roles.find((r) => r.name === role);
  const curProfile = current?.profiles?.find((p) => p.name === profile);
  const level = curProfile?.level ?? "中";

  // 该角色在指定档位对应的风格（角色支持该档才有值）
  const profileOfLevel = (r: RoleInfo | undefined, lv: string) =>
    r?.profiles?.find((p) => p.level === lv);

  // 点外部关闭下拉
  useEffect(() => {
    if (!open) return;
    const onDown = (ev: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(ev.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  const switchRole = async (r: string) => {
    if (r === role) return;
    setErr("");
    const rInfo = roles.find((x) => x.name === r);
    const first = rInfo?.profiles?.find((p) => p.available) ?? rInfo?.profiles?.[0];
    if (!first) {
      setErr(`「${rInfo?.label ?? r}」未安装：点下方「导入 DLC」安装内容包。`);
      return;
    }
    try {
      await api.setProfile(r, first.name);
      setOpen(false);
    } catch (e) {
      setErr(`切换失败：${(e as Error).message}`);
    }
  };

  const switchProfile = async (p: string) => {
    if (p === profile) return;
    setErr("");
    try {
      await api.setProfile(role, p);
      setOpen(false);
    } catch (e) {
      setErr(`「${STYLE_LABELS[p] ?? p}」未安装：点下方「导入 DLC」安装后即可切换。${(e as Error).message ? `（${(e as Error).message}）` : ""}`);
    }
  };

  const importDlc = async (f: File) => {
    setBusy(true);
    setErr("");
    setMsg("");
    try {
      const r = await api.importDlc(f);
      setMsg(
        `已导入 ${r.files?.length ?? 0} 个文件到 content\\pack\\${r.dir}${r.profile ? "，已自动启用「" + r.profile + "」" : ""}`,
      );
      if (r.role && r.profile && (r.role !== role || r.profile !== profile)) {
        await api.setProfile(r.role, r.profile).catch(() => undefined);
        setOpen(false);
      }
    } catch (e) {
      setErr(`导入失败：${(e as Error).message}`);
    } finally {
      setBusy(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  return (
    <div ref={rootRef} className="relative mb-3.5 rounded-[14px] border border-line bg-panel p-3.5">
      <button
        className="flex w-full items-center gap-2.5 text-left"
        onClick={() => setOpen((v) => !v)}
        title="切换角色与风格档"
      >
        <span
          className={`flex h-9 w-9 flex-none items-center justify-center rounded-[10px] border text-[16px] font-bold ${
            ROLE_RING_ACTIVE_CLS[role] ?? "border-line2 bg-accent/15"
          }`}
        >
          {(current?.label ?? role).slice(0, 1)}
        </span>
        <span className="min-w-0 flex-1">
          <span className="flex items-center gap-1.5 text-[14px] font-semibold">
            {current?.label ?? role}
            <span
              className={`rounded-md border px-1.5 py-px text-[10px] font-normal ${LEVEL_BADGE_CLS[level] ?? LEVEL_BADGE_CLS["中"]}`}
            >
              {STYLE_LABELS[profile] ?? profile} · {LEVEL_LABELS[level] ?? level}
            </span>
          </span>
          <span className="mt-0.5 block truncate text-[11px] text-muted">
            {styleDesc(role, profile) || "点击切换角色与风格"}
          </span>
        </span>
        {open ? (
          <ChevronUp size={14} className="flex-none text-faint" />
        ) : (
          <ChevronDown size={14} className="flex-none text-faint" />
        )}
      </button>

      {open && (
        <div className="absolute left-0 right-0 top-full z-30 mt-2 rounded-[12px] border border-line bg-panel shadow-xl shadow-black/50">
          <div className="flex flex-col gap-2 p-3">
            <div className="flex flex-col gap-0.5">
              <span className="px-1 text-[10px] tracking-wide text-faint">角色</span>
              {roles.map((r) => {
                const usable = (r.profiles ?? []).some((p) => p.available);
                return (
                  <button
                    key={r.name}
                    disabled={!usable}
                    title={usable ? undefined : `${r.label}需要安装对应 DLC（content\\pack\\）`}
                    onClick={() => void switchRole(r.name)}
                    className={`flex items-center gap-2 rounded-[6px] border px-2 py-1.5 text-left text-[12px] transition-colors ${
                      r.name === role
                        ? `${ROLE_RING_ACTIVE_CLS[r.name] ?? "border-line2 bg-accent/15"} text-text`
                        : usable
                          ? `border-transparent text-muted hover:bg-panel2 ${ROLE_RING_CLS[r.name] ?? ""}`
                          : "cursor-not-allowed border-transparent text-faint opacity-60"
                    }`}
                  >
                    <span className="min-w-0 flex-1">{r.label}</span>
                    {!usable && <span className="text-[10px]">未装</span>}
                    {r.name === role && <Check size={12} className="flex-none text-accent" />}
                  </button>
                );
              })}
            </div>

            <div className="flex flex-col gap-0.5">
              <span className="px-1 text-[10px] tracking-wide text-faint">风格档（按强度三档）</span>
              <div className="grid grid-cols-3 gap-1">
                {LEVELS.map((lv) => {
                  const p = profileOfLevel(current, lv);
                  const lit = !!p && p.available;
                  const selected = p?.name === profile;
                  return (
                    <button
                      key={lv}
                      disabled={!lit}
                      title={lit ? undefined : `${current?.label ?? role} 未提供该档位`}
                      onClick={() => p && void switchProfile(p.name)}
                      className={`flex items-center justify-center gap-1.5 rounded-[6px] border px-1 py-1.5 text-[12px] transition-colors ${
                        selected
                          ? "border-accent bg-accent font-semibold text-ink"
                          : lit
                            ? "border-line bg-panel2 text-muted hover:border-line2"
                            : "cursor-not-allowed border-line bg-panel2 text-faint opacity-40"
                      }`}
                    >
                      <span
                        className={`h-1.5 w-1.5 flex-none rounded-full ${
                          lit ? (LEVEL_DOT_CLS[lv] ?? LEVEL_DOT_CLS["中"]) : "bg-faint"
                        }`}
                      />
                      {LEVEL_LABELS[lv] ?? lv}
                    </button>
                  );
                })}
              </div>
            </div>

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
              disabled={busy}
              onClick={() => fileRef.current?.click()}
              className="w-full rounded-[6px] border border-dashed border-line px-2 py-1 text-[11px] text-muted transition-colors hover:border-line2 disabled:opacity-60"
            >
              {busy ? "导入中…" : "导入 DLC（.zip 或 .md，自动装进 content\\pack）"}
            </button>

            {err && <p className="text-[10px] leading-relaxed text-red-400">{err}</p>}
            {msg && <p className="text-[10px] leading-relaxed text-emerald-400">{msg}</p>}
          </div>
        </div>
      )}
    </div>
  );
}
