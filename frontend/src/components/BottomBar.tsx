import { Ban, Pause, Play } from "lucide-react";
import { doEstop, doResume, run } from "../commands";
import { useApp, useLayout } from "../store";

export default function BottomBar() {
  const s = useApp((st) => st.state);
  const estop = !!s?.estop;
  const sidebarW = useLayout((st) => st.sidebarW);
  const controlW = useLayout((st) => st.controlW);
  const mode = useLayout((st) => st.mode);
  // 宽屏：急停栏只占中间聊天栏宽度；中/窄屏铺满（侧栏/右栏走抽屉）
  const fullSpan = mode !== "wide";

  return (
    <div
      className="fixed bottom-0 z-10 flex h-14 items-center gap-4 border-t border-line bg-ink2 px-5"
      style={fullSpan ? { left: 0, right: 0 } : { left: sidebarW, right: controlW }}
    >
      <button
        className="rounded-[10px] border border-line bg-panel2 px-3.5 py-1.5 text-[13px] hover:border-line2"
        onClick={() => run("stop", {}, ["A", "B"])}
      >
        全部清零
      </button>
      <button
        className="rounded-[10px] border border-line bg-panel2 px-3.5 py-1.5 text-[13px] hover:border-line2"
        onClick={doResume}
      >
        解除急停
      </button>
      <button
        onClick={() => (estop ? doResume() : doEstop())}
        data-tour="estop"
        title={estop ? "恢复（解除急停）" : "暂停（急停：全部清零并暂停 AI）"}
        className={`absolute left-1/2 top-[-12px] h-[52px] w-[52px] -translate-x-1/2 rounded-full border border-line2 text-[22px] shadow-[0_4px_16px_rgba(247,217,122,0.25)] transition-colors ${
          estop ? "bg-panel2 text-text" : "bg-accent text-ink"
        }`}
      >
        <span className="mx-auto flex justify-center">{estop ? <Play size={22} /> : <Pause size={22} />}</span>
      </button>
      <span className="ml-auto text-xs text-muted">
        空格 = 急停
        <Ban size={12} className="ml-1 inline" />
      </span>
    </div>
  );
}
