from __future__ import annotations

import json
import tempfile
import wave
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any
import sys

import numpy as np

from .wav_utils import read_wav_info
from shared.logging_utils import log_event


@dataclass(frozen=True)
class AudioPreprocessConfig:
    enabled: bool = False
    enable_noise_gate: bool = True
    enable_trim: bool = True
    frame_ms: int = 30
    min_speech_ms: int = 400
    post_speech_padding_ms: int = 150
    noise_calibration_ms: int = 1000
    noise_gate_ratio: float = 3.0
    min_rms: float = 80.0
    save_debug_wav: bool = True
    debug_dir: Path | None = None


@dataclass(frozen=True)
class AudioPreprocessResult:
    raw_wav_path: Path
    clean_wav_path: Path | None
    used_for_payload_path: Path
    raw_duration_ms: int
    clean_duration_ms: int | None
    total_frames: int
    speech_frames: int
    muted_frames: int
    leading_frames_trimmed: int
    trailing_frames_trimmed: int
    trimmed_head_ms: int
    trimmed_tail_ms: int
    speech_duration_ms: int
    noise_floor_rms: float
    noise_floor_strategy: str
    gate_threshold_rms: float
    speech_peak_rms: float
    speech_mean_rms: float
    fallback_used: bool
    fallback_reason: str | None
    debug_json_path: Path | None = None

    def to_debug_dict(self) -> dict[str, Any]:
        data = asdict(self)
        for key in ("raw_wav_path", "clean_wav_path", "used_for_payload_path", "debug_json_path"):
            value = data.get(key)
            data[key] = str(value) if value is not None else None
        return data


class AudioPreprocessor:
    def __init__(self, config: AudioPreprocessConfig | None = None) -> None:
        self.config = config or AudioPreprocessConfig()

    def process_file(
        self,
        wav_path: str | Path,
        *,
        output_dir: str | Path | None = None,
    ) -> AudioPreprocessResult:
        raw_path = Path(wav_path)
        log_event(
            "audio_preprocess_started",
            raw_wav_path=str(raw_path),
            enabled=self.config.enabled,
            enable_noise_gate=self.config.enable_noise_gate,
            enable_trim=self.config.enable_trim,
            frame_ms=self.config.frame_ms,
        )
        try:
            wav_data = self._load_wav(raw_path)
            if not self.config.enabled:
                result = self._make_basic_result(
                    raw_path=raw_path,
                    wav_data=wav_data,
                    output_dir=output_dir,
                    fallback_reason="disabled",
                    fallback_used=True,
                    clean_wav_path=None,
                    used_for_payload_path=raw_path,
                )
                result = self._maybe_write_debug_json(result, raw_path=raw_path, output_dir=output_dir)
                self._log_preprocess_done(result)
                return result

            frame_rms = self._frame_rms(
                wav_data["pcm"],
                sample_rate=int(wav_data["sample_rate"]),
                frame_ms=self.config.frame_ms,
            )
            noise_floor_rms, noise_floor_strategy = self._estimate_noise_floor(frame_rms)
            gate_threshold_rms = max(noise_floor_rms * float(self.config.noise_gate_ratio), float(self.config.min_rms))
            total_frames = int(frame_rms.shape[0])
            speech_frames = int(np.count_nonzero(frame_rms >= gate_threshold_rms)) if total_frames else 0
            muted_frames = max(0, total_frames - speech_frames)

            if self.config.enable_noise_gate:
                wav_data = self._apply_noise_gate(
                    wav_data,
                    frame_rms=frame_rms,
                    gate_threshold_rms=gate_threshold_rms,
                )

            trim_result = self._apply_trim(
                wav_data,
                frame_rms=frame_rms,
                gate_threshold_rms=gate_threshold_rms,
                fallback_reason=None,
            )
            wav_data = trim_result["wav_data"]
            fallback_used = bool(trim_result["fallback_used"])
            fallback_reason = trim_result["fallback_reason"]

            clean_wav_path: Path | None = None
            used_for_payload_path = raw_path
            clean_duration_ms: int | None = None

            if not fallback_used:
                clean_result = self._write_clean_wav(raw_path, wav_data, output_dir=output_dir)
                if clean_result["fallback_used"]:
                    fallback_used = True
                    fallback_reason = clean_result["fallback_reason"]
                else:
                    clean_wav_path = clean_result["clean_wav_path"]
                    used_for_payload_path = clean_wav_path or raw_path
                    clean_duration_ms = clean_result["clean_duration_ms"]

            result = self._make_basic_result(
                raw_path=raw_path,
                wav_data=wav_data,
                output_dir=output_dir,
                fallback_reason=fallback_reason,
                fallback_used=fallback_used,
                clean_duration_ms=clean_duration_ms,
                clean_wav_path=clean_wav_path,
                used_for_payload_path=used_for_payload_path,
                total_frames=total_frames,
                speech_frames=speech_frames,
                muted_frames=muted_frames,
                noise_floor_rms=noise_floor_rms,
                noise_floor_strategy=noise_floor_strategy,
                gate_threshold_rms=gate_threshold_rms,
                speech_peak_rms=float(frame_rms.max()) if frame_rms.size else 0.0,
                speech_mean_rms=float(frame_rms.mean()) if frame_rms.size else 0.0,
                leading_frames_trimmed=int(trim_result["leading_frames_trimmed"]),
                trailing_frames_trimmed=int(trim_result["trailing_frames_trimmed"]),
                trimmed_head_ms=int(trim_result["trimmed_head_ms"]),
                trimmed_tail_ms=int(trim_result["trimmed_tail_ms"]),
                speech_duration_ms=int(trim_result["speech_duration_ms"]),
            )
            result = self._maybe_write_debug_json(result, raw_path=raw_path, output_dir=output_dir)
            self._log_preprocess_done(result)
            return result
        except Exception as exc:
            log_event(
                "audio_preprocess_failed",
                raw_wav_path=str(raw_path),
                exception_type=type(exc).__name__,
                message=str(exc),
                fallback_to_raw=True,
                level="warning",
            )
            raise

    def process_bytes(
        self,
        wav_bytes: bytes,
        *,
        output_dir: str | Path | None = None,
    ) -> AudioPreprocessResult:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
            tmp_file.write(wav_bytes)
            tmp_path = Path(tmp_file.name)
        try:
            return self.process_file(tmp_path, output_dir=output_dir)
        finally:
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)

    def _load_wav(self, wav_path: Path) -> dict[str, Any]:
        if not wav_path.exists():
            raise ValueError(f"Invalid wav file: path does not exist: {wav_path}")

        with wave.open(str(wav_path), "rb") as wav:
            sample_width = wav.getsampwidth()
            channels = wav.getnchannels()
            sample_rate = wav.getframerate()
            frame_count = wav.getnframes()
            raw_pcm = wav.readframes(frame_count)

        if sample_width != 2:
            raise ValueError(f"Unsupported wav sample width: expected 2 bytes, got {sample_width}")
        if channels not in {1, 2}:
            raise ValueError(f"Unsupported channel count: expected 1 or 2, got {channels}")
        if frame_count <= 0 or not raw_pcm:
            raise ValueError("Invalid wav file: no audio frames")

        expected_bytes = frame_count * channels * sample_width
        if len(raw_pcm) < expected_bytes:
            raise ValueError("Invalid wav file: truncated PCM data")

        pcm = np.frombuffer(raw_pcm[:expected_bytes], dtype="<i2")
        if channels > 1:
            pcm = pcm.reshape((-1, channels))

        duration_ms = int(frame_count * 1000 / sample_rate) if sample_rate else 0
        return {
            "path": wav_path,
            "sample_rate": sample_rate,
            "channels": channels,
            "sample_width": sample_width,
            "frame_count": frame_count,
            "duration_ms": duration_ms,
            "pcm": pcm,
        }

    def _make_basic_result(
        self,
        *,
        raw_path: Path,
        wav_data: dict[str, Any],
        output_dir: str | Path | None,
        fallback_reason: str | None,
        fallback_used: bool,
        clean_duration_ms: int | None = None,
        clean_wav_path: Path | None = None,
        used_for_payload_path: Path | None = None,
        total_frames: int | None = None,
        speech_frames: int | None = None,
        muted_frames: int | None = None,
        leading_frames_trimmed: int = 0,
        trailing_frames_trimmed: int = 0,
        trimmed_head_ms: int = 0,
        trimmed_tail_ms: int = 0,
        speech_duration_ms: int | None = None,
        noise_floor_rms: float = 0.0,
        noise_floor_strategy: str = "disabled",
        gate_threshold_rms: float = 0.0,
        speech_peak_rms: float = 0.0,
        speech_mean_rms: float = 0.0,
    ) -> AudioPreprocessResult:
        raw_duration_ms = int(wav_data["duration_ms"])
        raw_path = Path(raw_path)
        total_frames = int(total_frames if total_frames is not None else 0)
        speech_frames = int(speech_frames if speech_frames is not None else 0)
        muted_frames = int(muted_frames if muted_frames is not None else 0)
        speech_duration_ms = int(
            speech_duration_ms if speech_duration_ms is not None else (raw_duration_ms if speech_frames else 0)
        )

        clean_path: Path | None = clean_wav_path
        used_for_payload_path = used_for_payload_path or raw_path
        return AudioPreprocessResult(
            raw_wav_path=raw_path,
            clean_wav_path=clean_path,
            used_for_payload_path=used_for_payload_path,
            raw_duration_ms=raw_duration_ms,
            clean_duration_ms=clean_duration_ms,
            total_frames=total_frames,
            speech_frames=speech_frames,
            muted_frames=muted_frames,
            leading_frames_trimmed=leading_frames_trimmed,
            trailing_frames_trimmed=trailing_frames_trimmed,
            trimmed_head_ms=trimmed_head_ms,
            trimmed_tail_ms=trimmed_tail_ms,
            speech_duration_ms=speech_duration_ms,
            noise_floor_rms=noise_floor_rms,
            noise_floor_strategy=noise_floor_strategy,
            gate_threshold_rms=gate_threshold_rms,
            speech_peak_rms=speech_peak_rms,
            speech_mean_rms=speech_mean_rms,
            fallback_used=fallback_used,
            fallback_reason=fallback_reason,
            debug_json_path=None,
        )

    def _frame_rms(self, samples: np.ndarray, *, sample_rate: int, frame_ms: int) -> np.ndarray:
        if sample_rate <= 0:
            raise ValueError(f"Invalid wav file: unsupported sample rate {sample_rate}")
        frame_size = self._frame_size(sample_rate, frame_ms)
        if samples.ndim == 1:
            total_samples = samples.shape[0]
        else:
            total_samples = samples.shape[0]

        frame_values: list[float] = []
        for start in range(0, total_samples, frame_size):
            end = min(start + frame_size, total_samples)
            frame = samples[start:end]
            if frame.size == 0:
                continue
            frame_values.append(self._rms(frame))
        return np.asarray(frame_values, dtype=np.float64)

    def _rms(self, frame: np.ndarray) -> float:
        if frame.size == 0:
            return 0.0
        frame_float = frame.astype(np.float64, copy=False)
        return float(np.sqrt(np.mean(np.square(frame_float))))

    def _apply_noise_gate(
        self,
        wav_data: dict[str, Any],
        *,
        frame_rms: np.ndarray,
        gate_threshold_rms: float,
    ) -> dict[str, Any]:
        pcm = np.array(wav_data["pcm"], copy=True)
        if frame_rms.size == 0:
            wav_data["pcm"] = pcm
            return wav_data

        frame_size = self._frame_size(int(wav_data["sample_rate"]), self.config.frame_ms)
        for index, rms in enumerate(frame_rms):
            if rms < gate_threshold_rms:
                start = index * frame_size
                end = min(start + frame_size, pcm.shape[0])
                pcm[start:end] = 0

        wav_data["pcm"] = pcm
        return wav_data

    def _apply_trim(
        self,
        wav_data: dict[str, Any],
        *,
        frame_rms: np.ndarray,
        gate_threshold_rms: float,
        fallback_reason: str | None,
    ) -> dict[str, Any]:
        result: dict[str, Any] = {
            "wav_data": wav_data,
            "fallback_used": False,
            "fallback_reason": fallback_reason,
            "leading_frames_trimmed": 0,
            "trailing_frames_trimmed": 0,
            "trimmed_head_ms": 0,
            "trimmed_tail_ms": 0,
            "speech_duration_ms": int(wav_data["duration_ms"]),
        }

        if not self.config.enable_trim:
            return result

        speech_indices = np.flatnonzero(frame_rms >= gate_threshold_rms)
        if speech_indices.size == 0:
            result["fallback_used"] = True
            result["fallback_reason"] = "no_speech_detected"
            return result

        first_speech_frame = int(speech_indices[0])
        last_speech_frame = int(speech_indices[-1])
        speech_frame_count = last_speech_frame - first_speech_frame + 1
        speech_span_ms = int(speech_frame_count * self.config.frame_ms)
        if speech_span_ms < self.config.min_speech_ms:
            result["fallback_used"] = True
            result["fallback_reason"] = "speech_too_short"
            return result

        pre_padding_frames = max(0, int(round(100 / max(1, self.config.frame_ms))))
        post_padding_frames = max(0, int(round(self.config.post_speech_padding_ms / max(1, self.config.frame_ms))))

        start_frame = max(0, first_speech_frame - pre_padding_frames)
        end_frame = min(int(frame_rms.shape[0]), last_speech_frame + 1 + post_padding_frames)
        if end_frame <= start_frame:
            result["fallback_used"] = True
            result["fallback_reason"] = "invalid_trim_range"
            return result

        sample_rate = int(wav_data["sample_rate"])
        frame_size = self._frame_size(sample_rate, self.config.frame_ms)
        samples = np.asarray(wav_data["pcm"])
        start_sample = start_frame * frame_size
        end_sample = min(samples.shape[0], end_frame * frame_size)
        trimmed_pcm = samples[start_sample:end_sample]
        if trimmed_pcm.size == 0:
            result["fallback_used"] = True
            result["fallback_reason"] = "invalid_trimmed_audio"
            return result

        wav_data["pcm"] = trimmed_pcm
        result["leading_frames_trimmed"] = start_frame
        result["trailing_frames_trimmed"] = max(0, int(frame_rms.shape[0] - end_frame))
        result["trimmed_head_ms"] = int(start_frame * self.config.frame_ms)
        result["trimmed_tail_ms"] = int(max(0, int(frame_rms.shape[0] - end_frame)) * self.config.frame_ms)
        result["speech_duration_ms"] = int(trimmed_pcm.shape[0] * 1000 / sample_rate) if sample_rate else 0
        return result

    def _write_clean_wav(
        self,
        raw_path: Path,
        wav_data: dict[str, Any],
        *,
        output_dir: str | Path | None,
    ) -> dict[str, Any]:
        output_base = Path(output_dir) if output_dir is not None else raw_path.parent
        clean_path = output_base / f"{raw_path.stem}.clean.wav"
        clean_path.parent.mkdir(parents=True, exist_ok=True)

        sample_rate = int(wav_data["sample_rate"])
        channels = int(wav_data["channels"])
        sample_width = int(wav_data["sample_width"])
        pcm = np.asarray(wav_data["pcm"])
        pcm_bytes = pcm.astype("<i2", copy=False).tobytes()

        try:
            with wave.open(str(clean_path), "wb") as wav:
                wav.setnchannels(channels)
                wav.setsampwidth(sample_width)
                wav.setframerate(sample_rate)
                wav.writeframes(pcm_bytes)
        except Exception as exc:
            if clean_path.exists():
                clean_path.unlink(missing_ok=True)
            return {
                "fallback_used": True,
                "fallback_reason": f"invalid_clean_wav:{type(exc).__name__}",
                "clean_wav_path": None,
                "clean_duration_ms": None,
            }

        try:
            clean_info = read_wav_info(clean_path)
        except Exception as exc:
            clean_path.unlink(missing_ok=True)
            return {
                "fallback_used": True,
                "fallback_reason": f"invalid_clean_wav:{type(exc).__name__}",
                "clean_wav_path": None,
                "clean_duration_ms": None,
            }

        if (
            clean_info.sample_rate != sample_rate
            or clean_info.channels != channels
            or clean_info.sample_width != sample_width
            or clean_info.duration_ms <= 0
            or clean_info.frame_count <= 0
            or not clean_path.exists()
            or clean_path.stat().st_size <= 44
        ):
            clean_path.unlink(missing_ok=True)
            return {
                "fallback_used": True,
                "fallback_reason": "invalid_clean_wav",
                "clean_wav_path": None,
                "clean_duration_ms": None,
            }

        return {
            "fallback_used": False,
            "fallback_reason": None,
            "clean_wav_path": clean_path,
            "clean_duration_ms": clean_info.duration_ms,
        }

    def _maybe_write_debug_json(
        self,
        result: AudioPreprocessResult,
        *,
        raw_path: Path,
        output_dir: str | Path | None,
    ) -> AudioPreprocessResult:
        if not self.config.save_debug_wav:
            return result

        debug_dir = Path(self.config.debug_dir or output_dir or raw_path.parent)
        debug_dir.mkdir(parents=True, exist_ok=True)
        debug_path = debug_dir / f"{raw_path.stem}.debug.json"

        debug_payload = {
            "raw_wav_path": str(result.raw_wav_path),
            "clean_wav_path": str(result.clean_wav_path) if result.clean_wav_path else None,
            "used_for_payload_path": str(result.used_for_payload_path),
            "raw_duration_ms": result.raw_duration_ms,
            "clean_duration_ms": result.clean_duration_ms,
            "trimmed_head_ms": result.trimmed_head_ms,
            "trimmed_tail_ms": result.trimmed_tail_ms,
            "noise_floor_rms": result.noise_floor_rms,
            "noise_floor_strategy": result.noise_floor_strategy,
            "gate_threshold_rms": result.gate_threshold_rms,
            "speech_peak_rms": result.speech_peak_rms,
            "speech_mean_rms": result.speech_mean_rms,
            "total_frames": result.total_frames,
            "speech_frames": result.speech_frames,
            "muted_frames": result.muted_frames,
            "leading_frames_trimmed": result.leading_frames_trimmed,
            "trailing_frames_trimmed": result.trailing_frames_trimmed,
            "speech_duration_ms": result.speech_duration_ms,
            "fallback_used": result.fallback_used,
            "fallback_reason": result.fallback_reason,
        }

        try:
            debug_path.write_text(json.dumps(debug_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:
            print(
                f"[audio_preprocessor] WARNING: failed to write debug json for {raw_path}: {exc}",
                file=sys.stderr,
            )
            return result

        return replace(result, debug_json_path=debug_path)

    def _log_preprocess_done(self, result: AudioPreprocessResult) -> None:
        log_event(
            "audio_preprocess_done",
            raw_wav_path=str(result.raw_wav_path),
            clean_wav_path=str(result.clean_wav_path) if result.clean_wav_path else None,
            used_for_payload_path=str(result.used_for_payload_path),
            raw_duration_ms=result.raw_duration_ms,
            clean_duration_ms=result.clean_duration_ms,
            trimmed_head_ms=result.trimmed_head_ms,
            trimmed_tail_ms=result.trimmed_tail_ms,
            noise_floor_rms=result.noise_floor_rms,
            noise_floor_strategy=result.noise_floor_strategy,
            gate_threshold_rms=result.gate_threshold_rms,
            speech_peak_rms=result.speech_peak_rms,
            speech_mean_rms=result.speech_mean_rms,
            total_frames=result.total_frames,
            speech_frames=result.speech_frames,
            muted_frames=result.muted_frames,
            fallback_used=result.fallback_used,
            fallback_reason=result.fallback_reason,
        )

    def _frame_size(self, sample_rate: int, frame_ms: int) -> int:
        return max(1, int(sample_rate * frame_ms / 1000))

    def _estimate_noise_floor(self, frame_rms: np.ndarray) -> tuple[float, str]:
        if frame_rms.size == 0:
            return 0.0, "fallback_zero"

        percentile_noise = float(np.percentile(frame_rms, 20))
        calibration_frames = max(1, int(round(self.config.noise_calibration_ms / max(1, self.config.frame_ms))))

        if frame_rms.size <= calibration_frames:
            noise_floor = percentile_noise
            return self._sanitize_noise_floor(noise_floor), "short_audio_percentile"

        initial_window = frame_rms[:calibration_frames]
        initial_noise = float(np.median(initial_window))

        if initial_noise <= percentile_noise:
            noise_floor = initial_noise
            strategy = "initial_calibration"
        else:
            noise_floor = percentile_noise
            strategy = "global_low_percentile"

        return self._sanitize_noise_floor(noise_floor), strategy

    def _sanitize_noise_floor(self, value: float) -> float:
        if not np.isfinite(value) or value < 0:
            return 0.0
        return float(value)