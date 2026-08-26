import { api } from "./api";
import { useApp, useChat } from "./store";
import type { ManualResult } from "./types";

/** 联动开启时动作同时发到 A/B 两通道 */
export function targets(ch: "A" | "B"): ("A" | "B")[] {
  return useApp.getState().linkOn ? ["A", "B"] : [ch];
}

export function labels(res: ManualResult | null | undefined): string {
  if (!res) return "";
  const parts: string[] = [];
  for (const e of res.executed ?? []) parts.push("▶ " + e.label);
  for (const d of res.dropped ?? []) parts.push("✖ " + d.reason);
  return parts.join("\n");
}

function report(text: string) {
  if (text.trim()) useChat.getState().push({ role: "sys", text: text.trim() });
}

/** 对目标通道逐个执行动作并汇总结果 */
export async function run(
  op: string,
  params: Record<string, unknown>,
  chs: ("A" | "B")[],
): Promise<void> {
  let text = "";
  for (const t of chs) {
    try {
      text += labels(await api.manual({ op, channel: t, ...params })) + "\n";
    } catch (e) {
      text += `✖ 请求失败: ${String(e)}\n`;
    }
  }
  report(text);
}

export async function doEstop(): Promise<void> {
  try {
    await api.estop();
  } catch {
    /* 状态由 ws 推送刷新 */
  }
  useChat.getState().push({ role: "sys", text: "⚠ 急停：全部清零、波形停止、AI 循环暂停" });
}

export async function doResume(): Promise<void> {
  await api.resume();
  useChat.getState().push({ role: "sys", text: "急停已解除" });
}
