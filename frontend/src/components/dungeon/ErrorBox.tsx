/** 面板错误框：按错误类别给动作。旧档（save_format 等）→「旧版存档不兼容，请新开」+ 新开按钮。 */
import { useT } from "../../i18n";
import type { PanelError } from "../DungeonPanel";

export default function ErrorBox({ error, onClose, onNew }: { error: PanelError; onClose: () => void; onNew?: () => void }) {
  const t = useT();
  const isEstop = error.kind === "estop";
  const cls = isEstop ? "border-bad bg-bad/20 text-bad" : "border-bad/40 bg-bad/10 text-bad";
  return (
    <div className={`mb-3 rounded-lg border p-3 text-sm ${cls}`} role="alert">
      <div className="flex items-start justify-between gap-2">
        <p className="flex-1">{t(error.text)}</p>
        <button onClick={onClose} className="text-xs text-bad/70 hover:text-bad">
          ✕
        </button>
      </div>
      {(error.kind === "old_save" || error.kind === "run_over") && onNew && (
        <button onClick={onNew} className="mt-2 rounded-lg border border-bad/50 px-3 py-1 text-xs hover:bg-bad/10">
          {t("新开一局")}
        </button>
      )}
    </div>
  );
}
