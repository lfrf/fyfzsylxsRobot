from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from pathlib import Path
import math
from time import time
from typing import Literal

from raspirobot.utils import ensure_dir, utc_compact_timestamp
from shared.logging_utils import log_event

from .input_provider import AudioCaptureError, AudioFrame, AudioInputProvider
from .recorder import WavRecorder
from .vad import EnergyVAD
from .wav_utils import WavInfo


@dataclass(frozen=True)
class Utterance:
    wav_path: Path
    started_at: float
    ended_at: float
    duration_ms: int
    frame_count: int
    wav_info: WavInfo


@dataclass(frozen=True)
class ListenResult:
    kind: Literal["utterance", "timeout", "capture_error", "input_ended"]
    utterance: Utterance | None = None
    error: str | None = None
    elapsed_ms: int | None = None
    returncode: int | None = None
    frames_emitted: int = 0
    stderr_tail: str = ""


class AudioListenWorker:
    def __init__(
        self,
        *,
        input_provider: AudioInputProvider,
        vad: EnergyVAD,
        output_dir: str | Path,
    ) -> None:
        self.input_provider = input_provider
        self.vad = vad
        self.output_dir = ensure_dir(output_dir)
        self.recorder = WavRecorder(
            output_dir=self.output_dir,
            sample_rate=input_provider.sample_rate,
            channels=input_provider.channels,
            sample_width=input_provider.sample_width,
        )

    def listen_once(
        self,
        *,
        speech_start_timeout_seconds: float | None = None,
        rms_threshold_override: float | None = None,
        speech_start_frames_override: int | None = None,
        dynamic_noise_enabled: bool = False,
        dynamic_noise_calibration_ms: int = 0,
        dynamic_noise_ratio: float = 2.2,
    ) -> Utterance | None:
        result = self.listen_once_result(
            speech_start_timeout_seconds=speech_start_timeout_seconds,
            rms_threshold_override=rms_threshold_override,
            speech_start_frames_override=speech_start_frames_override,
            dynamic_noise_enabled=dynamic_noise_enabled,
            dynamic_noise_calibration_ms=dynamic_noise_calibration_ms,
            dynamic_noise_ratio=dynamic_noise_ratio,
        )
        return result.utterance if result.kind == "utterance" else None

    def listen_once_result(
        self,
        *,
        speech_start_timeout_seconds: float | None = None,
        rms_threshold_override: float | None = None,
        speech_start_frames_override: int | None = None,
        dynamic_noise_enabled: bool = False,
        dynamic_noise_calibration_ms: int = 0,
        dynamic_noise_ratio: float = 2.2,
    ) -> ListenResult:
        log_event(
            "listening_started",
            sample_rate=self.input_provider.sample_rate,
            channels=self.input_provider.channels,
            frame_ms=self.input_provider.frame_ms,
            output_dir=str(self.output_dir),
            speech_start_timeout_seconds=speech_start_timeout_seconds,
        )
        listen_started_at = time()
        config = self.vad.config
        speech_start_frames = max(1, int(speech_start_frames_override or config.speech_start_frames))
        rms_threshold = float(rms_threshold_override if rms_threshold_override is not None else config.rms_threshold)
        base_rms_threshold = rms_threshold
        calibration_target_ms = max(0, int(dynamic_noise_calibration_ms if dynamic_noise_enabled else 0))
        calibration_frames: list[AudioFrame] = []
        calibration_ms = 0
        calibrated = calibration_target_ms <= 0
        pre_roll_frames = max(0, int(config.pre_roll_ms / max(1, config.frame_ms)))
        pre_roll: deque[AudioFrame] = deque(maxlen=pre_roll_frames)
        utterance_frames: list[AudioFrame] = []
        voiced_streak = 0
        silence_ms = 0
        recorded_ms = 0
        started_at: float | None = None
        frames_seen = 0

        try:
            for frame in self.input_provider.frames():
                frames_seen += 1
                if (
                    started_at is None
                    and speech_start_timeout_seconds is not None
                    and time() - listen_started_at >= speech_start_timeout_seconds
                ):
                    log_event(
                        "speech_start_timeout",
                        timeout_seconds=speech_start_timeout_seconds,
                    )
                    return ListenResult(
                        kind="timeout",
                        elapsed_ms=int((time() - listen_started_at) * 1000),
                        frames_emitted=frames_seen,
                    )

                if not calibrated:
                    calibration_frames.append(frame)
                    calibration_ms += frame.duration_ms
                    pre_roll.append(frame)
                    if calibration_ms < calibration_target_ms:
                        continue
                    noise_floor_rms = self._noise_floor_rms(calibration_frames)
                    dynamic_threshold = noise_floor_rms * max(0.0, float(dynamic_noise_ratio))
                    rms_threshold = max(rms_threshold, dynamic_threshold)
                    calibrated = True
                    log_event(
                        "vad_dynamic_noise_calibrated",
                        calibration_ms=calibration_ms,
                        noise_floor_rms=round(noise_floor_rms, 2),
                        base_rms_threshold=round(base_rms_threshold, 2),
                        effective_rms_threshold=round(rms_threshold, 2),
                        dynamic_noise_ratio=dynamic_noise_ratio,
                    )
                    continue

                voiced = self.vad.rms(frame) >= rms_threshold

                if started_at is None:
                    if voiced:
                        voiced_streak += 1
                        if voiced_streak >= speech_start_frames:
                            started_at = frame.timestamp or time()
                            log_event(
                                "speech_started",
                                sample_rate=frame.sample_rate,
                                channels=frame.channels,
                                rms=round(self.vad.rms(frame), 2),
                            )
                            utterance_frames.extend(pre_roll)
                            utterance_frames.append(frame)
                            recorded_ms = sum(item.duration_ms for item in utterance_frames)
                            silence_ms = 0
                        else:
                            pre_roll.append(frame)
                    else:
                        voiced_streak = 0
                        pre_roll.append(frame)
                    continue

                utterance_frames.append(frame)
                recorded_ms += frame.duration_ms
                if voiced:
                    silence_ms = 0
                else:
                    silence_ms += frame.duration_ms

                if silence_ms >= config.silence_timeout_ms:
                    log_event(
                        "speech_ended",
                        reason="silence_timeout",
                        silence_ms=silence_ms,
                        recorded_ms=recorded_ms,
                    )
                    return ListenResult(
                        kind="utterance",
                        utterance=self._save_utterance(utterance_frames, started_at),
                        elapsed_ms=int((time() - listen_started_at) * 1000),
                        frames_emitted=frames_seen,
                    )

                if recorded_ms >= int(config.max_utterance_seconds * 1000):
                    log_event(
                        "speech_ended",
                        reason="max_utterance_seconds",
                        recorded_ms=recorded_ms,
                    )
                    return ListenResult(
                        kind="utterance",
                        utterance=self._save_utterance(utterance_frames, started_at),
                        elapsed_ms=int((time() - listen_started_at) * 1000),
                        frames_emitted=frames_seen,
                    )
        except AudioCaptureError as exc:
            log_event(
                "audio_capture_error",
                error=str(exc),
                returncode=exc.returncode,
                elapsed_ms=exc.elapsed_ms,
                frames_emitted=exc.frames_emitted,
                stderr_tail=exc.stderr_tail,
                level="error",
            )
            return ListenResult(
                kind="capture_error",
                error=str(exc),
                elapsed_ms=exc.elapsed_ms,
                returncode=exc.returncode,
                frames_emitted=exc.frames_emitted,
                stderr_tail=exc.stderr_tail,
            )

        if started_at is not None and utterance_frames:
            log_event("speech_ended", reason="input_stream_ended")
            return ListenResult(
                kind="utterance",
                utterance=self._save_utterance(utterance_frames, started_at),
                elapsed_ms=int((time() - listen_started_at) * 1000),
                frames_emitted=frames_seen,
            )

        log_event(
            "audio_input_ended_without_speech",
            elapsed_ms=int((time() - listen_started_at) * 1000),
            frames_emitted=frames_seen,
        )
        return ListenResult(
            kind="input_ended",
            elapsed_ms=int((time() - listen_started_at) * 1000),
            frames_emitted=frames_seen,
        )

    def _noise_floor_rms(self, frames: list[AudioFrame]) -> float:
        values = sorted(self.vad.rms(frame) for frame in frames)
        if not values:
            return 0.0
        cutoff = max(1, int(math.ceil(len(values) * 0.3)))
        low_values = values[:cutoff]
        return sum(low_values) / len(low_values)

    def _save_utterance(self, frames: list[AudioFrame], started_at: float) -> Utterance:
        ended_at = time()
        filename = f"utterance_{utc_compact_timestamp()}_{int(time() * 1000) % 1000000:06d}.wav"
        wav_info = self.recorder.save_frames(frames, filename=filename)
        file_size = wav_info.path.stat().st_size if wav_info.path.exists() else None
        log_event(
            "utterance_saved",
            wav_path=str(wav_info.path),
            duration_ms=wav_info.duration_ms,
            file_size_bytes=file_size,
            sample_rate=wav_info.sample_rate,
            channels=wav_info.channels,
            frame_count=wav_info.frame_count,
        )
        return Utterance(
            wav_path=wav_info.path,
            started_at=started_at,
            ended_at=ended_at,
            duration_ms=wav_info.duration_ms,
            frame_count=len(frames),
            wav_info=wav_info,
        )
