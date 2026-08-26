# -*- coding: utf-8 -*-
"""麦克风检测：录音 + 响度门限 + 本地 Whisper 转写。

- 后台持续监听麦克风，每 interval_s 检查一次响度；
- 响度超过 threshold 才截取片段，用本地 Whisper（faster-whisper，CPU）转写；
- 转写结果通过 on_text 回调交给主程序，作为「玩家反应信号」注入 AI 上下文。
- 全程本机处理，音频不出本机。
"""
import asyncio
import logging
import time
from pathlib import Path

logger = logging.getLogger("ai-for-coyote.audio")


class AudioManager:
    def __init__(self, cfg, on_text=None, on_moan=None) -> None:
        c = cfg.get("audio", {})
        self.enabled = bool(c.get("enabled", False))
        self.interval_s = float(c.get("interval_s", 4.0))
        self.threshold = float(c.get("threshold", 0.02))
        self.min_segment_s = float(c.get("min_segment_s", 0.8))
        self.model_size = str(c.get("model_size", "small"))
        self.device = c.get("device") or None
        self.language = str(c.get("language", "zh"))
        # 呻吟分级：电平 >= threshold*倍数 算高声呻吟/惨叫；同类信号冷却期
        self.moan_high_multiple = float(c.get("moan_high_multiple", 8.0))
        self.moan_cooldown_s = float(c.get("moan_cooldown_s", 5.0))
        self.silence_timeout_s = float(c.get("silence_timeout_s", 90.0))
        self.on_text = on_text
        self.on_moan = on_moan

        self.whisper = None
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        self._loop: asyncio.AbstractEventLoop | None = None
        self.last_text = ""
        self.last_ts = 0.0
        self.level = 0.0
        self.last_sound_ts = 0.0  # 最近一次电平超过门限的时刻（判断持续无声）
        self.error = ""
        self._last_moan_ts = 0.0
        self._last_moan_kind = ""

    def _emit(self, fn, *args) -> None:
        """把回调安全地调度回主事件循环（转写在子线程执行；兼容 sync/async 回调）。"""
        if not (self._loop and self._loop.is_running()):
            return
        try:

            async def _call():
                result = fn(*args)
                if asyncio.iscoroutine(result):
                    await result

            asyncio.run_coroutine_threadsafe(_call(), self._loop)
        except Exception:  # noqa: BLE001
            logger.exception("回调调度失败")

    # ---------- 生命周期 ----------
    async def start(self) -> None:
        if not self.enabled:
            return
        try:
            import faster_whisper  # noqa: F401
            import sounddevice as sd  # noqa: F401
        except ImportError as exc:
            self.error = f"缺少依赖（pip install faster-whisper sounddevice）：{exc}"
            logger.error("麦克风不可用：%s", self.error)
            return
        self._stop = asyncio.Event()
        self._loop = asyncio.get_running_loop()
        self._task = asyncio.create_task(self._listen_loop())
        logger.info("麦克风监听已启动：间隔 %ss，模型 %s", self.interval_s, self.model_size)

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            self._task.cancel()
            self._task = None

    # ---------- 监听循环 ----------
    async def _listen_loop(self) -> None:
        import numpy as np
        import sounddevice as sd

        sr = 16000
        chunk_s = self.interval_s
        buffer: list[np.ndarray] = []

        def callback(indata, frames, time_info, status):  # noqa: ARG001
            buffer.append(indata.copy())

        try:
            with sd.InputStream(
                samplerate=sr, channels=1, dtype="float32",
                callback=callback, device=self.device,
            ):
                while not self._stop.is_set():
                    try:
                        await asyncio.wait_for(self._stop.wait(), timeout=chunk_s)
                        break
                    except asyncio.TimeoutError:
                        pass
                    if not buffer:
                        continue
                    audio = np.concatenate(buffer)
                    buffer.clear()
                    self.level = float(np.sqrt(np.mean(audio ** 2)))
                    if self.level >= self.threshold:
                        self.last_sound_ts = time.time()
                        await asyncio.to_thread(self._transcribe, audio, sr)
        except Exception as exc:  # noqa: BLE001
            self.error = str(exc)
            logger.exception("麦克风监听异常")

    def _transcribe(self, audio, sr: int) -> None:
        """截取有效片段并转写（线程内执行，避免阻塞）。"""
        try:
            from faster_whisper import WhisperModel

            if self.whisper is None:
                logger.info("加载 Whisper 模型 %s …", self.model_size)
                self.whisper = WhisperModel(
                    self.model_size, device="cpu", compute_type="int8"
                )
            # 找有响度的连续段（简单门限切段）
            import numpy as np

            idx = np.where(np.abs(audio) >= self.threshold)[0]
            if len(idx) < int(self.min_segment_s * sr):
                return
            seg = audio[idx[0]: idx[-1] + 1]
            if len(seg) < sr // 4:  # 短于 0.25s 忽略
                return
            segments, info = self.whisper.transcribe(  # noqa: F841
                seg, language=self.language, beam_size=1,
                vad_filter=True, initial_prompt="以下是普通话内容。",
            )
            text = "".join(s.text for s in segments).strip()
            if not text:
                self._report_moan(seg)
                return
            self.last_text = text
            self.last_ts = time.time()
            logger.info("麦克风转写：%s", text)
            if self.on_text:
                self._emit(self.on_text, text)
        except Exception as exc:  # noqa: BLE001
            self.error = str(exc)
            logger.exception("转写失败")

    def _report_moan(self, seg) -> None:
        """无文字片段 = 呻吟/叫声：按电平分级上报（带冷却，防刷屏）。"""
        import numpy as np

        level = float(np.sqrt(np.mean(np.asarray(seg, dtype="float32") ** 2)))
        kind = "high" if level >= self.threshold * self.moan_high_multiple else "low"
        now = time.time()
        if (
            now - self._last_moan_ts < self.moan_cooldown_s
            and kind == self._last_moan_kind
        ):
            return
        self._last_moan_ts = now
        self._last_moan_kind = kind
        logger.info("麦克风呻吟信号：%s（电平 %.3f）", kind, level)
        if self.on_moan:
            self._emit(self.on_moan, kind, level)

    # ---------- 状态 ----------
    def to_state(self) -> dict:
        return {
            "enabled": self.enabled,
            "running": bool(self._task and not self._task.done()),
            "last_text": self.last_text,
            "last_ts": self.last_ts,
            "level": round(self.level, 4),
            "last_sound_ts": self.last_sound_ts,
            "silent": (time.time() - self.last_sound_ts) > self.silence_timeout_s,
            "threshold": self.threshold,
            "model_size": self.model_size,
            "error": self.error,
        }
