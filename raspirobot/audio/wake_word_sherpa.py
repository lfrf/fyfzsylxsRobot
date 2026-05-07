"""
SherpaOnnxWakeWordProvider

使用 sherpa-onnx keyword spotting 模型实现本地中文唤醒词检测。
后台线程通过 sounddevice 读取麦克风，检测到唤醒词后设置标志位。
主循环通过 poll() 查询是否触发。
"""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from shared.logging_utils import log_event

logger = logging.getLogger(__name__)


@dataclass
class SherpaOnnxWakeWordConfig:
    # 模型目录
    model_dir: str = "models/sherpa-onnx-kws-zipformer-zh-en-3M-2025-12-20"
    # 关键词文件，每行一个唤醒词
    keywords_file: str = ""
    # 期望唤醒词；如果模型返回其它关键词，忽略。
    expected_keyword: str = "你好小星"
    # 使用 chunk-8（低延迟）还是 chunk-16（高精度）
    chunk_size: int = 8
    # 是否使用 int8 量化模型（树莓派推荐开启）
    use_int8: bool = True
    # sounddevice 麦克风设备编号或名称。None 表示使用系统默认输入。
    device: int | str | None = 1
    # 采样率，sherpa-onnx kws 要求 16000
    sample_rate: int = 16000
    # 每次送入 KWS 的样本块；1600 = 100ms @ 16kHz
    block_size: int = 1600
    num_threads: int = 2
    max_active_paths: int = 8
    num_trailing_blanks: int = 1
    keywords_score: float = 3.0
    keywords_threshold: float = 0.08
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
        self._stream_lock = threading.Lock()
        self._running = False
        self._thread: threading.Thread | None = None
        self._last_trigger_time: float = 0.0

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        with self._lock:
            self._triggered = False
        self._thread = threading.Thread(
            target=self._detection_loop,
            daemon=True,
            name="wake-word-detector",
        )
        self._thread.start()
        log_event(
            "wake_word_detector_started",
            model_dir=self.config.model_dir,
            wake_keyword=self.config.expected_keyword,
            device=self.config.device,
        )

    def stop(self) -> None:
        if not self._running and self._thread is None:
            return
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=3.0)
            self._thread = None
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
            import numpy as np
            import sounddevice as sd
        except ImportError:
            logger.error("wake word dependencies missing. Run: pip install sherpa-onnx sounddevice numpy")
            self._running = False
            return

        try:
            keyword_spotter = self._build_keyword_spotter(sherpa_onnx)
            stream = keyword_spotter.create_stream()
        except Exception as exc:
            logger.error("wake_word_detector_init_failed: %s", exc)
            self._running = False
            return

        keywords_file = self._resolve_keywords_file()
        self._log_keywords_file(keywords_file)

        def callback(indata: Any, frames: int, callback_time: Any, status: Any) -> None:
            nonlocal stream
            del frames, callback_time
            if status:
                logger.debug("wake_word_input_status: %s", status)
            if not self._running:
                return

            samples = indata[:, 0].astype(np.float32)
            with self._stream_lock:
                stream.accept_waveform(self.config.sample_rate, samples)
                while keyword_spotter.is_ready(stream):
                    if hasattr(keyword_spotter, "decode_stream"):
                        keyword_spotter.decode_stream(stream)
                    else:
                        keyword_spotter.decode(stream)

                result = keyword_spotter.get_result(stream)
                keyword = self._result_to_text(result)
                if not keyword:
                    return
                if self.config.expected_keyword and self.config.expected_keyword not in keyword:
                    log_event(
                        "wake_word_ignored",
                        keyword=keyword,
                        expected_keyword=self.config.expected_keyword,
                    )
                    stream = self._reset_stream(keyword_spotter, stream)
                    return

                import time

                now = time.time()
                if now - self._last_trigger_time < self.config.cooldown_seconds:
                    return

                self._last_trigger_time = now
                with self._lock:
                    self._triggered = True
                log_event(
                    "wake_word_detected",
                    keyword=keyword,
                    expected_keyword=self.config.expected_keyword,
                )
                stream = self._reset_stream(keyword_spotter, stream)

        log_event(
            "wake_word_detection_loop_started",
            sample_rate=self.config.sample_rate,
            block_size=self.config.block_size,
            device=self.config.device,
            wake_keyword=self.config.expected_keyword,
            keywords_file=str(keywords_file),
        )

        try:
            with sd.InputStream(
                samplerate=self.config.sample_rate,
                channels=1,
                dtype="float32",
                blocksize=self.config.block_size,
                callback=callback,
                device=self.config.device,
            ):
                while self._running:
                    sd.sleep(100)
        except Exception as exc:
            logger.error("wake_word_detection_loop_error: %s", exc)
        finally:
            self._running = False
            log_event("wake_word_detection_loop_stopped")

    def _build_keyword_spotter(self, sherpa_onnx):
        model_dir = self._resolve_model_dir()
        chunk = self.config.chunk_size
        int8 = self.config.use_int8

        encoder = str(model_dir / f"encoder-epoch-13-avg-2-chunk-{chunk}-left-64{'.int8' if int8 else ''}.onnx")
        decoder = str(model_dir / f"decoder-epoch-13-avg-2-chunk-{chunk}-left-64.onnx")
        joiner = str(model_dir / f"joiner-epoch-13-avg-2-chunk-{chunk}-left-64{'.int8' if int8 else ''}.onnx")
        tokens = str(model_dir / "tokens.txt")

        return sherpa_onnx.KeywordSpotter(
            encoder=encoder,
            decoder=decoder,
            joiner=joiner,
            tokens=tokens,
            keywords_file=str(self._resolve_keywords_file()),
            num_threads=self.config.num_threads,
            max_active_paths=self.config.max_active_paths,
            num_trailing_blanks=self.config.num_trailing_blanks,
            keywords_score=self.config.keywords_score,
            keywords_threshold=self.config.keywords_threshold,
        )

    def _resolve_keywords_file(self) -> Path:
        if self.config.keywords_file:
            keywords_file = Path(self.config.keywords_file)
            if keywords_file.is_absolute() or keywords_file.exists():
                return keywords_file
            return self._project_root() / keywords_file
        return self._resolve_model_dir() / "keywords.txt"

    def _resolve_model_dir(self) -> Path:
        model_dir = Path(self.config.model_dir)
        if model_dir.is_absolute() or model_dir.exists():
            return model_dir
        return self._project_root() / model_dir

    def _project_root(self) -> Path:
        return Path(__file__).resolve().parents[2]

    def _log_keywords_file(self, keywords_file: Path) -> None:
        try:
            content = keywords_file.read_text(encoding="utf-8").strip()
        except Exception as exc:
            log_event(
                "wake_word_keywords_read_failed",
                keywords_file=str(keywords_file),
                error=str(exc),
                level="error",
            )
            return
        log_event(
            "wake_word_keywords_loaded",
            keywords_file=str(keywords_file),
            wake_keyword=self.config.expected_keyword,
            keywords_text=content,
        )
        if self.config.expected_keyword and self.config.expected_keyword not in content:
            log_event(
                "wake_word_expected_keyword_missing",
                keywords_file=str(keywords_file),
                wake_keyword=self.config.expected_keyword,
                level="warning",
            )

    def _result_to_text(self, result: Any) -> str:
        if result is None:
            return ""
        if isinstance(result, str):
            return result.strip()
        keyword = getattr(result, "keyword", None)
        if keyword:
            return str(keyword).strip()
        return str(result).strip()

    def _reset_stream(self, keyword_spotter: Any, stream: Any) -> Any:
        if hasattr(keyword_spotter, "reset_stream"):
            keyword_spotter.reset_stream(stream)
            return stream
        return keyword_spotter.create_stream()
