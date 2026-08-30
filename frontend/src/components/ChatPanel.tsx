import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { useApp, useChat } from "../store";
import { LEVEL_BADGE_CLS, LEVEL_LABELS } from "../roleTheme";

export default function ChatPanel() {
  const messages = useChat((st) => st.messages);
  const pushMsg = useChat((st) => st.push);
  const clearChat = useChat((st) => st.clear);
  const autopilot = useApp((st) => st.state?.autopilot ?? false);
  const relay = useApp((st) => st.state?.relay);
  const paired = relay?.status === "paired";
  const enabled = useApp((st) => st.state?.enabled_channels);
  const role = useApp((st) => st.state?.role ?? "触手");
  const profile = useApp((st) => st.state?.profile ?? "纯爱");
  const level = useApp((st) => st.state?.profile_level ?? "中");
  const [pairUrl, setPairUrl] = useState("");
  const boxRef = useRef<HTMLDivElement>(null);

  // 切换角色/风格档时插一条系统分隔消息，防上下文串戏
  const roleKeyRef = useRef(`${role}·${profile}`);
  useEffect(() => {
    const key = `${role}·${profile}`;
    if (roleKeyRef.current !== key) {
      roleKeyRef.current = key;
      pushMsg({
        role: "sys",
        text: `—— 已切换至 ${role} · ${LEVEL_LABELS[level] ?? level} ——`,
      });
    }
  }, [role, profile, level, pushMsg]);

  useEffect(() => {
    boxRef.current?.scrollTo({ top: boxRef.current.scrollHeight });
  }, [messages]);

  useEffect(() => {
    if (paired) return;
    api
      .network()
      .then((n) => setPairUrl(n.pair_url ?? ""))
      .catch(() => {});
  }, [paired]);

  const toggle = async () => {
    try {
      await api.setAutopilot(!autopilot);
    } catch {
      /* 状态由 ws 推送刷新 */
    }
  };

  return (
    <aside className="flex min-h-0 flex-col border-l border-line bg-ink2">
      <div className="flex flex-none items-center border-b border-line px-4 py-2">
        <div className="flex items-center gap-2 rounded-lg border border-line bg-panel2 px-2.5 py-1">
          <span className="text-[11px] text-faint">当前主题</span>
          <span className="text-[12px] font-semibold text-text">{role}</span>
          <span
            className={`rounded-md border px-1.5 py-px text-[10px] ${LEVEL_BADGE_CLS[level] ?? LEVEL_BADGE_CLS["中"]}`}
          >
            {LEVEL_LABELS[level] ?? level}
          </span>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <span className="text-[11px] text-muted">自动运行</span>
          <button
            onClick={() => void toggle()}
            title={autopilot ? "停止自动运行" : "开始自动运行（AI 自主回合，摄像头/麦克风跟随启停）"}
            className={`relative h-5 w-9 flex-none rounded-full transition-colors ${
              autopilot ? "bg-accent" : "bg-ink3 border border-line"
            }`}
          >
            <span
              className={`absolute top-1/2 h-4 w-4 -translate-y-1/2 rounded-full transition-all ${
                autopilot ? "left-[18px] bg-ink" : "left-[2px] bg-muted"
              }`}
            />
          </button>
          <button
            onClick={() => {
              if (!window.confirm("清空对话历史？将清空聊天记录与 AI 的记忆上下文，设备强度不受影响。")) return;
              api
                .clearHistory()
                .then(() => {
                  clearChat();
                  pushMsg({ role: "sys", text: "—— 对话历史已清空 ——" });
                })
                .catch(() => {});
            }}
            className="rounded-md border border-line bg-panel2 px-2 py-1 text-[11px] text-muted transition-colors hover:border-line2 hover:text-text"
          >
            清空
          </button>
        </div>
      </div>
      {!paired ? (
        <div className="flex min-h-0 flex-1 flex-col items-center justify-center gap-2 px-6 py-6 text-center">
          <img
            src="/api/qrcode.png"
            alt="配对二维码"
            className="w-64 rounded-lg border border-line bg-white p-2"
            onError={(e) => ((e.target as HTMLImageElement).style.display = "none")}
          />
          <div className="mt-2 text-[13px] font-semibold text-muted">手机打开 DG-LAB 4.0 App 扫码配对</div>
          <div className="mt-1 text-[11px] text-warn">⚠️ 配对后请在 App 里打开「输出」开关（解除屏蔽），否则设备不会有感觉</div>
          {pairUrl && (
            <a
              href={pairUrl}
              target="_blank"
              rel="noreferrer"
              className="mt-0.5 block max-w-full break-all text-[10px] text-accent/80 hover:text-accent"
            >
              {pairUrl}
            </a>
          )}
          <div className="mt-1.5 text-[10px] text-faint">连接成功后 3 秒，AI 会主动开场</div>
        </div>
      ) : (
        <div ref={boxRef} className="flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto p-3.5">
          {enabled !== undefined && !enabled.A && !enabled.B && (
            <div className="self-center rounded-xl border border-bad/50 bg-bad/10 px-3 py-2 text-center text-[11px] text-bad">
              ⚠️ 所有通道都已关闭，AI 不会输出任何刺激——请在左侧通道卡打开至少一个通道
            </div>
          )}
          {messages.map((m, i) => (
            <div key={i} className="flex flex-col">
              <div
                className={`max-w-[90%] whitespace-pre-wrap break-words rounded-xl px-3 py-2 text-[13px] leading-relaxed ${
                  m.role === "user"
                    ? "self-end border border-line2 bg-accent/15 rounded-br"
                    : m.role === "ai"
                      ? "self-start mr-auto border border-line bg-ink3 rounded-bl"
                      : "self-center text-[11px] text-muted"
                }`}
              >
                {m.text}
              </div>
              {m.actions && (
                <div
                  className={`mt-1 flex max-w-[90%] flex-wrap gap-1 border-t border-dashed border-line pt-1 ${
                    m.role === "user" ? "self-end" : "self-start"
                  }`}
                >
                  {m.actions.split("\n").filter(Boolean).map((a, j) => (
                    <span
                      key={j}
                      className="rounded-md border border-line bg-panel2 px-1.5 py-0.5 text-[10px] text-accent2"
                    >
                      {a}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </aside>
  );
}
