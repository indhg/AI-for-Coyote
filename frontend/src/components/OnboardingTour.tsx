import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import type { Tour, TourStep } from "../onboarding";
import { useT } from "../i18n";

/**
 * 新手引导浮窗引擎（v2：元素自带发光，不再画坐标框）。
 * 高亮 = 给目标元素加 .tour-glow（沿其自带边框发光）+ 抬升 z 到遮罩之上；
 * 固定容器（如 BottomBar）里的目标，自动抬升最近定位祖先。
 * 卡片固定底部居中，不追元素位置 → 无偏移问题。
 */
export default function OnboardingTour({
  tour,
  view,
  onView,
  onFinish,
}: {
  tour: Tour;
  view: "control" | "settings" | "pair" | "help";
  onView: (v: "control" | "settings" | "pair" | "help") => void;
  onFinish: () => void;
}) {
  const t = useT();
  const [idx, setIdx] = useState(0);
  const timer = useRef<number | null>(null);
  const raised = useRef<HTMLElement[]>([]);

  const step: TourStep = tour.steps[Math.min(idx, tour.steps.length - 1)];
  const last = idx >= tour.steps.length - 1;

  // 切换视图（延迟等渲染）
  useEffect(() => {
    if (step.view && step.view !== view) {
      onView(step.view);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [idx]);

  // 高亮当前步骤的目标元素（加类 + 抬升 z），清理上一步的；
  // 锚点缺失时立即跳过（不再用可被清理的计时器，避免卡死）
  useEffect(() => {
    if (timer.current) window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => {
      cleanup();
      if (!step.anchor) return;
      const el = document.querySelector(step.anchor) as HTMLElement | null;
      if (!el) {
        console.warn(`[OnboardingTour] 锚点缺失，自动跳过该步: ${step.anchor}`);
        next();
        return;
      }
      el.scrollIntoView({ block: "center", behavior: "smooth" });
      const pos = window.getComputedStyle(el).position;
      el.classList.add("tour-glow");
      if (pos === "static") {
        el.classList.add("tour-raise"); // 静态元素：relative + z
      } else {
        el.classList.add("tour-raise-z"); // 已定位元素：只抬 z
      }
      // 若目标在 fixed/absolute 容器里（如 BottomBar），抬升最近定位祖先（只抬 z，不改变定位）
      let anc = el.parentElement;
      while (anc && anc !== document.body) {
        const p = window.getComputedStyle(anc).position;
        if (p === "fixed" || p === "absolute" || p === "sticky") {
          anc.classList.add("tour-raise-z");
          raised.current.push(anc);
          break;
        }
        anc = anc.parentElement;
      }
    }, 250);
    return () => {
      if (timer.current) window.clearTimeout(timer.current);
      cleanup();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [idx, view]);

  const cleanup = () => {
    document.querySelectorAll(".tour-glow").forEach((e) => {
      e.classList.remove("tour-glow", "tour-raise", "tour-raise-z");
    });
    raised.current.forEach((e) => e.classList.remove("tour-raise"));
    raised.current = [];
  };

  const next = () => {
    if (last) {
      cleanup();
      onFinish();
    } else {
      setIdx(idx + 1);
    }
  };
  const prev = () => setIdx(Math.max(0, idx - 1));

  if (idx >= tour.steps.length) return null; // 全部跳过完毕

  // 正文渲染：支持换行 + 网址高亮 + **加粗**
  const renderBody = (text: string) => {
    const parts = text.split(/(https?:\/\/[^\s]+)/g);
    return parts.map((p, i) => {
      if (/^https?:/.test(p)) {
        return (
          <span key={i} className="font-semibold text-accent">
            {p}
          </span>
        );
      }
      return p.split(/\*\*([^*]+)\*\*/g).map((seg, j) =>
        j % 2 === 1 ? (
          <span key={`${i}-${j}`} className="font-semibold text-accent">
            {seg}
          </span>
        ) : (
          <span key={`${i}-${j}`}>{seg}</span>
        ),
      );
    });
  };

  // 遮罩（z-60，挡住一切交互）
  const overlay = <div className="fixed inset-0 z-[60] bg-black/60" />;
  // 步骤浮窗单独 portal 到 body（z-80，永远在最上层）；急停步骤往右偏移避开底部居中按钮
  // 步骤浮窗单独 portal 到 body（z-80，永远在最上层）；急停步骤只往右偏移一点避开底部按钮
  const cardPos =
    step.side === "right"
      ? {
          left: "calc(50% + 200px)",
          transform: "translateX(-50%)",
          bottom: 24,
          maxWidth: "min(400px, calc(100vw - 480px))",
        }
      : { left: "50%", transform: "translateX(-50%)", bottom: 24 };
  const card = (
    <div
      className="fixed z-[80] w-[min(400px,90vw)] rounded-[14px] border border-accent/60 bg-panel p-4 shadow-[0_8px_40px_rgba(0,0,0,0.6)]"
      style={cardPos}
    >
      <div className="mb-1 flex items-center gap-2">
        <span className="text-[13px] font-bold text-accent">
          {idx + 1}/{tour.steps.length} · {t(step.title)}
        </span>
      </div>
      <p className="mb-3 whitespace-pre-line text-[12px] leading-relaxed text-text">{renderBody(t(step.body))}</p>
      <div className="flex items-center justify-between">
        <button
          onClick={() => {
            cleanup();
            onFinish();
          }}
          className="text-[12px] text-faint hover:text-muted"
        >
          {t("跳过")}
        </button>
        <div className="flex items-center gap-2">
          {idx > 0 && (
            <button
              onClick={prev}
              className="rounded-lg border border-line bg-panel2 px-3 py-1.5 text-[12px] text-muted hover:border-line2"
            >
              {t("上一步")}
            </button>
          )}
          <button
            onClick={next}
            className="rounded-lg bg-accent px-4 py-1.5 text-[12px] font-semibold text-ink"
          >
            {last ? t("完成") : t("下一步")}
          </button>
        </div>
      </div>
    </div>
  );

  return (
    <>
      {createPortal(overlay, document.body)}
      {createPortal(card, document.body)}
    </>
  );
}
