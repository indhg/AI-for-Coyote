import { useEffect, useMemo, useRef } from "react";
import { useApp } from "../store";

/** A/B 通道配色（A=金色，B=蓝） */
interface ChannelColor {
  main: string;
  bright: string;
  fillTop: string;
}
const COLORS: Record<"A" | "B", ChannelColor> = {
  A: { main: "#f7d97a", bright: "#ffe59a", fillTop: "rgba(247,217,122,0.16)" },
  B: { main: "#4fc3f7", bright: "#7ed6ff", fillTop: "rgba(79,195,247,0.16)" },
};

/**
 * 实时波形示波器：同一张图叠加显示 A/B 两通道当前波形的波形
 * （A=金色曲线，B=蓝色曲线），播放时各自带播放头滚动。
 * 帧格式：每帧 8 字节十六进制，前 4 字节 A 通道、后 4 字节 B 通道振幅(00~64)。
 */
export default function WaveformCard() {
  const s = useApp((st) => st.state);
  const lastPreset = useApp((st) => st.lastPreset);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  const presetOf = (ch: "A" | "B") =>
    s?.presets?.find((p) => p.name === lastPreset[ch]) ?? s?.presets?.[0] ?? null;
  const presetA = presetOf("A");
  const presetB = presetOf("B");
  // 只按波形名 memo 帧数组：ws 状态推送（~每 100ms）不会触发 canvas 循环重建
  const framesA = useMemo(() => presetA?.frames ?? [], [presetA?.name]);
  const framesB = useMemo(() => presetB?.frames ?? [], [presetB?.name]);
  const pulsingA = !!s?.pulse_active?.A;
  const pulsingB = !!s?.pulse_active?.B;
  const frameMs = s?.playback?.frame_ms ?? 100;

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let raf = 0;

    const drawChannel = (
      ch: "A" | "B",
      frames: string[],
      pulsing: boolean,
      color: ChannelColor,
    ) => {
      const w = canvas.width;
      const h = canvas.height;
      const n = frames.length;
      if (!n) return;
      const sample = (f: string) => {
        const hex = ch === "A" ? f.slice(0, 2) : f.slice(4, 6);
        return parseInt(hex, 16) / 100;
      };

      // 参考 App 样式：柱子按脉冲分段——宽度∝段内帧数（时长），高度∝段内峰值（强度）
      interface Seg {
        start: number;
        end: number;
        peak: number;
      }
      const segs: Seg[] = [];
      let cur: Seg | null = null;
      for (let i = 0; i < n; i++) {
        const a = sample(frames[i]);
        if (a > 0.05) {
          if (!cur) cur = { start: i, end: i, peak: a };
          else {
            cur.end = i;
            cur.peak = Math.max(cur.peak, a);
          }
        } else if (cur) {
          segs.push(cur);
          cur = null;
        }
      }
      if (cur) segs.push(cur);
      if (!segs.length) return;

      const areaW = w - 24;
      // 基准线：画布下部 30% 处，柱子从这里向上生长
      const baseY = h * 0.7;
      const maxH = baseY - 10;
      const cycle = (n * frameMs) / 1000;
      const headX = pulsing ? ((performance.now() / 1000) % cycle) / cycle * w : 0;

      for (const seg of segs) {
        const segFrames = seg.end - seg.start + 1;
        const x = 12 + (seg.start / n) * areaW;
        const bw = Math.max(2, (segFrames / n) * areaW - 1);
        const bh = Math.max(3, seg.peak * maxH);
        const dim = pulsing && x > headX ? 0.45 : 1;
        const grad = ctx.createLinearGradient(0, baseY - bh, 0, baseY);
        grad.addColorStop(0, color.bright);
        grad.addColorStop(1, color.main);
        ctx.globalAlpha = dim;
        ctx.fillStyle = grad;
        ctx.shadowColor = color.main;
        ctx.shadowBlur = pulsing ? 8 : 3;
        ctx.beginPath();
        const r = Math.min(2, bw / 2, bh / 2);
        ctx.moveTo(x, baseY);
        ctx.lineTo(x, baseY - bh + r);
        ctx.quadraticCurveTo(x, baseY - bh, x + r, baseY - bh);
        ctx.lineTo(x + bw - r, baseY - bh);
        ctx.quadraticCurveTo(x + bw, baseY - bh, x + bw, baseY - bh + r);
        ctx.lineTo(x + bw, baseY);
        ctx.closePath();
        ctx.fill();
      }
      ctx.shadowBlur = 0;
      ctx.globalAlpha = 1;

      if (pulsing) {
        // 播放头竖线（细、带光晕）
        ctx.beginPath();
        ctx.strokeStyle = color.bright;
        ctx.lineWidth = 1.5;
        ctx.shadowColor = color.bright;
        ctx.shadowBlur = 10;
        ctx.moveTo(headX, 8);
        ctx.lineTo(headX, baseY);
        ctx.stroke();
        ctx.shadowBlur = 0;
      }
    };

    const draw = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      // 基准线：画布下部 30% 处，常驻显示
      ctx.strokeStyle = "rgba(168,168,168,0.35)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(8, canvas.height * 0.7);
      ctx.lineTo(canvas.width - 8, canvas.height * 0.7);
      ctx.stroke();

      // 只在有波形播放时画柱子，否则留空（只显示基准线）
      if (!pulsingA && !pulsingB) {
        return;
      }
      if (pulsingB && framesB.length) {
        drawChannel("B", framesB, pulsingB, COLORS.B);
      }
      if (pulsingA && framesA.length) {
        // A 通道画在上层（A 使用更频繁，优先看清）
        drawChannel("A", framesA, pulsingA, COLORS.A);
      }
    };

    const loop = () => {
      draw();
      raf = requestAnimationFrame(loop);
    };
    draw();
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [framesA, framesB, pulsingA, pulsingB, frameMs]);

  const legend = (ch: "A" | "B", presetName: string | null, pulsing: boolean) => {
    const c = COLORS[ch];
    return (
      <span className="flex items-center gap-1 text-[11px] text-muted">
        <span className="h-2 w-2 flex-none rounded-full" style={{ background: c.main }} />
        <span>{ch}</span>
        <span className="max-w-[8rem] truncate">{presetName ?? "未选择波形"}</span>
        {pulsing && <span className="text-[10px] text-faint">播放中</span>}
      </span>
    );
  };

  return (
    <div className="flex min-h-0 flex-col rounded-[14px] border border-line bg-panel p-3">
      <div className="mb-1.5 flex flex-none items-center justify-between gap-2">
        <h3 className="text-[12px] font-semibold tracking-[1.5px] text-muted">实时波形</h3>
        <div className="flex items-center gap-3">
          {legend("A", presetA?.name ?? null, pulsingA)}
          {legend("B", presetB?.name ?? null, pulsingB)}
        </div>
      </div>
      <canvas
        ref={canvasRef}
        width={960}
        height={480}
        className="min-h-0 w-full flex-1 rounded-lg border border-line bg-ink3"
      />
    </div>
  );
}
