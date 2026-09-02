import { useEffect, useState } from "react";
import { useApp } from "../store";
import { useT } from "../i18n";

/** 公告浮窗：右下角卡片；勾选「下次更新前不再提示」后按版本号记忆，升级到新版本会再弹。 */
const STORE_KEY = "notice_dismissed_version";

export default function NoticeToast({
  onDismissed,
  force,
}: {
  onDismissed?: () => void;
  /** true = 用户从帮助里主动点开公告，无视"本版已看"记忆强制弹出 */
  force?: boolean;
}) {
  const t = useT();
  const version = useApp((st) => st.state?.config_info?.version ?? "");
  const [closed, setClosed] = useState(false);
  const [dontShow, setDontShow] = useState(false);

  // 用户主动点「公告」时重新弹出（清掉上次的 closed）
  useEffect(() => {
    if (force) setClosed(false);
  }, [force]);

  if (closed || !version) return null;
  let dismissedVersion = "";
  try {
    dismissedVersion = window.localStorage.getItem(STORE_KEY) ?? "";
  } catch {
    /* 隐私模式或禁用存储时公告仍可正常使用 */
  }
  if (!force && dismissedVersion === version) return null;

  const dismiss = () => {
    if (dontShow && version) {
      try {
        window.localStorage.setItem(STORE_KEY, version);
      } catch {
        /* 非核心的公告记忆失败不影响关闭公告 */
      }
    }
    setClosed(true);
    onDismissed?.();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="max-h-[90vh] w-[360px] max-w-[92vw] overflow-y-auto rounded-[16px] border border-accent/60 bg-panel p-5 shadow-[0_8px_40px_rgba(0,0,0,0.6)]">
        <div className="mb-3 flex items-center">
          <span className="text-[18px] font-bold text-accent">{t("公告")}</span>
        </div>
        <div className="mb-4 space-y-3 text-[13px] leading-relaxed text-text">
          <section className="rounded-[10px] border border-accent/50 bg-accent/5 px-3 py-2.5">
            <p className="mb-1 text-center text-[15px] font-bold text-accent">
              {t("本软件完全免费")}
            </p>
            <p className="text-center leading-relaxed">
              <span className="font-bold text-bad">{t("⚠ 任何以本软件名义要求付费的版本均为盗版")}</span>
            </p>
            <p className="mt-1.5 border-t border-line/60 pt-1.5 text-[12px] text-muted">
              {t("未经授权，禁止转载、倒卖、二次分发或制作衍生发布包。")}
            </p>
          </section>
          <section>
            <h4 className="mb-1 font-semibold text-accent">{t("内容版本说明")}</h4>
            <p>{t("拓展包及其他 NSFW 内容属于独立的 18+ 内容范围，与主仓库分开维护。地牢内容目前仍在开发中，暂不作为公开发布内容。")}</p>
          </section>
          <section>
            <h4 className="mb-1 font-semibold text-accent">{t("作者主页")}</h4>
            <p>
              {t("欢迎通过作者主页获取更新信息或支持作者：")}{" "}
              <a
                href="https://x.com/cinnanirch"
                target="_blank"
                rel="noreferrer"
                className="font-semibold text-accent hover:underline"
              >
                x.com/cinnanirch
              </a>
            </p>
          </section>
        </div>
        <div className="flex items-center justify-between gap-2">
          <label className="flex items-center gap-1.5 text-[11px] text-muted">
            <input
              type="checkbox"
              checked={dontShow}
              onChange={(e) => setDontShow(e.target.checked)}
              className="h-3 w-3 accent-[#f7d97a]"
            />
            {t("下次更新前不再提示")}
          </label>
          <button
            onClick={dismiss}
            className="rounded-lg bg-accent px-4 py-1.5 text-[13px] font-semibold text-ink transition-opacity hover:opacity-90"
          >
            {t("知道了")}
          </button>
        </div>
      </div>
    </div>
  );
}
