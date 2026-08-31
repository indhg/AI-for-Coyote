import { useState } from "react";
import { useApp } from "../store";

/** 公告浮窗：右下角卡片；勾选「下次更新前不再提示」后按版本号记忆，升级到新版本会再弹。 */
const STORE_KEY = "notice_dismissed_version";

export default function NoticeToast({ onDismissed }: { onDismissed?: () => void }) {
  const version = useApp((st) => st.state?.config_info?.version ?? "");
  const [closed, setClosed] = useState(false);
  const [dontShow, setDontShow] = useState(false);

  if (closed || !version) return null;
  if (window.localStorage.getItem(STORE_KEY) === version) return null;

  const dismiss = () => {
    if (dontShow && version) {
      window.localStorage.setItem(STORE_KEY, version);
    }
    setClosed(true);
    onDismissed?.();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="w-[360px] max-w-[92vw] rounded-[16px] border border-accent/60 bg-panel p-5 shadow-[0_8px_40px_rgba(0,0,0,0.6)]">
        <div className="mb-3 flex items-center">
          <span className="text-[18px] font-bold text-accent">公告</span>
        </div>
        <ul className="mb-4 space-y-2.5 text-[13px] leading-relaxed text-text">
          <li className="flex items-baseline gap-1.5">
            <span className="h-1.5 w-1.5 flex-none self-center rounded-full bg-white" />
            <span>
              本项目
              <span className="text-[17px] font-bold text-accent">完全免费</span>
              开源，任何收费渠道均为盗版。
            </span>
          </li>
          <li className="flex items-baseline gap-1.5">
            <span className="h-1.5 w-1.5 flex-none self-center rounded-full bg-white" />
            <span>
              这里是作者的推特主页，欢迎来支持喵~{" "}
              <a
                href="https://x.com/cinnanirch"
                target="_blank"
                rel="noreferrer"
                className="font-semibold text-accent hover:underline"
              >
                点这里
              </a>
            </span>
          </li>
        </ul>
        <div className="flex items-center justify-between gap-2">
          <label className="flex items-center gap-1.5 text-[11px] text-muted">
            <input
              type="checkbox"
              checked={dontShow}
              onChange={(e) => setDontShow(e.target.checked)}
              className="h-3 w-3 accent-[#f7d97a]"
            />
            下次更新前不再提示
          </label>
          <button
            onClick={dismiss}
            className="rounded-lg bg-accent px-4 py-1.5 text-[13px] font-semibold text-ink transition-opacity hover:opacity-90"
          >
            知道了
          </button>
        </div>
      </div>
    </div>
  );
}
