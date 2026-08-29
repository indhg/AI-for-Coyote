# -*- coding: utf-8 -*-
"""摄像头采集：周期截帧，供多模态模型观察玩家反应（阶段 3）。

- 配置 camera.enabled 开启；无摄像头环境不启用即可（不 import cv2）。
- 画面按 camera.interval_s 周期刷新，最新帧保存为 JPEG 并提供 base64。
"""
import asyncio
import atexit
import base64
import logging
import time

logger = logging.getLogger("ai-for-coyote.camera")


class Camera:
    def __init__(self, cfg) -> None:
        c = cfg.get("camera", {})
        self.enabled = bool(c.get("enabled", False))
        self.index = int(c.get("index", 0))
        self.interval_s = float(c.get("interval_s", 1.5))
        self.dark_threshold = float(c.get("dark_threshold", 20.0))  # 平均亮度低于此值视为画面黑暗
        self.vision_prompt = str(
            c.get(
                "vision_prompt",
                "观察画面中玩家的反应（姿态、手部动作、表情、衣物的状态），"
                "用一两句话总结，并据此决定是否调整刺激。",
            )
        )
        self.cap = None
        self.latest_jpeg: bytes | None = None
        self.last_ts: float = 0.0
        self.mean_brightness: float = 0.0  # 最新帧平均亮度（0~255）
        self._task: asyncio.Task | None = None
        self.error: str = ""
        atexit.register(self._release_sync)  # 进程异常退出时释放摄像头

    # ---------- 生命周期 ----------
    async def start(self) -> None:
        if not self.enabled:
            return
        try:
            import cv2  # 延迟导入：未启用摄像头时无需安装 opencv
        except ImportError as exc:
            self.error = f"缺少 opencv-python：{exc}"
            logger.error("摄像头不可用：%s", self.error)
            return
        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                self.cap = cv2.VideoCapture(self.index)
                if not self.cap.isOpened():
                    raise RuntimeError(f"无法打开摄像头 index={self.index}")
                self.error = ""
                self._task = asyncio.create_task(self._capture_loop())
                logger.info("摄像头已启动：index=%s 间隔=%ss", self.index, self.interval_s)
                return
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                if self.cap is not None:
                    try:
                        self.cap.release()
                    except Exception:  # noqa: BLE001
                        pass
                    self.cap = None
                logger.warning("摄像头打开失败（第 %d 次重试）：%s", attempt + 1, exc)
                await asyncio.sleep(0.5)
        self.error = str(last_exc or "未知错误")
        logger.error("摄像头启动失败：%s", self.error)

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task  # 等采集循环真正退出再释放，避免立刻重开冲突
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
            self._task = None
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        self.latest_jpeg = None  # 清掉残留帧，让 has_frame 如实反映停用状态
        self.last_ts = 0.0

    def _release_sync(self) -> None:
        """atexit 兜底：异常退出也释放摄像头。"""
        try:
            if self.cap is not None:
                self.cap.release()
                self.cap = None
        except Exception:  # noqa: BLE001
            pass

    async def _capture_loop(self) -> None:
        import cv2

        while True:
            try:
                ok, frame = self.cap.read()
                if ok:
                    self.mean_brightness = float(frame.mean())
                    # 限制最长边 1280，控制体积
                    h, w = frame.shape[:2]
                    longest = max(h, w)
                    if longest > 1280:
                        scale = 1280 / longest
                        frame = cv2.resize(
                            frame, (int(w * scale), int(h * scale)),
                            interpolation=cv2.INTER_AREA,
                        )
                    ok, buf = cv2.imencode(
                        ".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80]
                    )
                    if ok:
                        self.latest_jpeg = buf.tobytes()
                        self.last_ts = time.time()
            except Exception as exc:  # noqa: BLE001
                logger.warning("截帧失败: %s", exc)
            await asyncio.sleep(self.interval_s)

    # ---------- 数据 ----------
    def base64(self) -> str | None:
        if not self.latest_jpeg:
            return None
        return base64.b64encode(self.latest_jpeg).decode("ascii")

    def has_frame(self) -> bool:
        return self.latest_jpeg is not None

    def to_state(self) -> dict:
        return {
            "enabled": self.enabled,
            "has_frame": self.has_frame(),
            "last_ts": self.last_ts,
            "interval_s": self.interval_s,
            "mean_brightness": round(self.mean_brightness, 2),
            "dark": self.has_frame() and self.mean_brightness < self.dark_threshold,
            "dark_threshold": self.dark_threshold,
            "error": self.error,
        }
