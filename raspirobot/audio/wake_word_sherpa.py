"""
SherpaOnnxWakeWordProvider

使用 sherpa-onnx keyword spotting 模型实现本地中文唤醒词检测。
后台线程持续从麦克风读取音频，检测到唤醒词后设置标志位。
主循环通过 poll() 查询是否触发。
"""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from pathlib import Path

from shared.logging_utils import log_event

logger = logging.getLogger(__name__)


@dataclass
class SherpaOnnxWakeWordConfig:
    # 模型目录
    model_dir: str = "models/sherpa-onnx-kws-zipformer-zh-en-3M-2025-12-20"
    # 关键词文件，每行一个唤醒词
    keywords_file: str = ""
    # 使用 chunk-8（低延迟）还是 chunk-16（高精度）
    chunk_size: int = 8
    # 是否使用 int8 量化模型（树莓派推荐开启）
    use_int8: bool = True
    # 麦克风设备（arecord 格式）
    capture_device: str = "plughw:CARD=Lite,DEV=0"
    # 采样率，sherpa-onnx kws 要求 16000
    sample_rate: int = 16000
    # 检测到唤醒词后的冷却时间（秒），防止重复触发
    cooldown_seconds: float = 2.0


class SherpaOnnxWakeWordProvider:
    """
    实现 WakeWordProvider 协议。
    后台线程持续监听麦克风，检测到唤醒词后 poll() 返回 True。
    """

    def __init__(self, config: SherpaOnnxWakeWordConfig | None = None) -> None:
        self.config = config or SherpaOnnxWakeWordConfig()
        self._triggered = False
        self._lock = threading.Lock()
        self._running = False
        self._thread: threading.Thread | None = None
        self._last_trigger_time: float = 0.0

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._detection_loop,
            daemon=True,
            name="wake-word-detector",
        )
        self._thread.start()
        log_event("wake_word_detector_started", model_dir=self.config.model_dir)

    def stop(self) -> None:
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=3.0)
        log_event("wake_word_detector_stopped")

    def poll(self) -> bool:
        """返回 True 表示检测到唤醒词，同时清除标志位。"""
        with self._lock:
            triggered = self._triggered
            self._triggered = False
        return triggered

    # ------------------------------------------------------------------
    # 内部：检测循环
    # ------------------------------------------------------------------

    def _detection_loop(self) -> None:
        try:
            import sherpa_onnx
        except ImportError:
            logger.error("sherpa_onnx not installed. Run: pip install sherpa-onnx")
            self._running = False
            return

        try:
            keyword_spotter = self._build_keyword_spotter(sherpa_onnx)
        except Exception as exc:
            logger.error("wake_word_detector_init_failed: %s", exc)
            self._running = False
            return

        try:
            mic = self._build_mic(sherpa_onnx)
        except Exception as exc:
            logger.error("wake_word_mic_init_failed: %s", exc)
            self._running = False
            return

        stream = keyword_spotter.create_stream()
        log_event("wake_word_detection_loop_started")

        try:
            mic.start()
            while self._running:
                samples = mic.read(self.config.sample_rate // 10)  # 100ms 块
                if samples is None or len(samples) == 0:
                    continue
                stream.accept_waveform(self.config.sample_rate, samples)
                while keyword_spotter.is_ready(stream):
                    keyword_spotter.decode(stream)
                result = keyword_spotter.get_result(stream)
                if result.keyword:
                    import time
                    now = time.time()
                    if now - self._last_trigger_time >= self.config.cooldown_seconds:
                        self._last_trigger_time = now
                        with self._lock:
                            self._triggered = True
                        log_event(
                            "wake_word_detected",
                            keyword=result.keyword,
                        )
                        # 重置流，避免重复触发
                        stream = keyword_spotter.create_stream()
        except Exception as exc:
            logger.error("wake_word_detection_loop_error: %s", exc)
        finally:
            try:
                mic.stop()
            except Exception:
                pass
            log_event("wake_word_detection_loop_stopped")

    def _build_keyword_spotter(self, sherpa_onnx):
        model_dir = Path(self.config.model_dir)
        chunk = self.config.chunk_size
        int8 = self.config.use_int8

        encoder = str(model_dir / f"encoder-epoch-13-avg-2-chunk-{chunk}-left-64{'.int8' if int8 else ''}.onnx")
        decoder = str(model_dir / f"decoder-epoch-13-avg-2-chunk-{chunk}-left-64.onnx")
        joiner = str(model_dir / f"joiner-epoch-13-avg-2-chunk-{chunk}-left-64{'.int8' if int8 else ''}.onnx")
        tokens = str(model_dir / "tokens.txt")

        keywords_file = self.config.keywords_file
        if not keywords_file:
            keywords_file = str(model_dir / "keywords.txt")

        return sherpa_onnx.KeywordSpotter(
            encoder=encoder,
            decoder=decoder,
            joiner=joiner,
            tokens=tokens,
            keywords_file=keywords_file,
            num_threads=2,
            max_active_paths=4,
            keywords_score=1.0,
            keywords_threshold=0.25,
            provider="cpu",
        )

    def _build_mic(self, sherpa_onnx):
        return sherpa_onnx.Microphone(device_name=self.config.capture_device)
