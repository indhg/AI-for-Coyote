/**
 * 深渊路网 · mid/窄屏底部抽屉壳（D26 §四）。
 * fixed，底边留出 68px 给 BottomBar（h-14 + 急停圆钮上探 12px），不遮急停；Esc / 点遮罩 / 收起钮关闭。
 */
import { useEffect } from "react";
import { ChevronDown } from "lucide-react";
import { useT } from "../../i18n";

export default function RouteSheet({ open, onClose, children }: { open: boolean; onClose: () => void; children: React.ReactNode }) {
  const t = useT();
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <>
      <div className="fixed inset-x-0 top-0 z-[55] bg-black/40" style={{ bottom: 68 }} onClick={onClose} aria-hidden />
      <div
        role="dialog"
        aria-modal="true"
        aria-label={t("深渊路网")}
        className="dg-sheet-up fixed inset-x-0 z-[60] flex flex-col overflow-hidden rounded-t-[16px] border border-line bg-panel shadow-[0_-8px_32px_rgba(0,0,0,0.5)]"
        style={{ bottom: 68, height: "min(78vh, calc(100vh - 68px - 12px))" }}
      >
        <div className="flex flex-none items-center justify-between border-b border-line px-3 py-2">
          <span className="text-[12px] font-semibold tracking-[1.5px] text-muted">{t("深渊路网")}</span>
          <button
            type="button"
            onClick={onClose}
            className="flex h-8 items-center gap-1 rounded-md border border-line bg-panel2 px-2 text-[11px] text-muted hover:border-line2 hover:text-text"
          >
            {t("收起路网")} <ChevronDown size={12} />
          </button>
        </div>
        <div className="flex min-h-0 flex-1 flex-col overflow-hidden">{children}</div>
      </div>
    </>
  );
}
