from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from pathlib import Path
from time import time

from raspirobot.utils import ensure_dir, utc_compact_timestamp

from .input_provider import AudioFrame, AudioInputProvider
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

    def listen_once(self) -> Utterance | None:
        config = self.vad.config
        pre_roll_frames = max(0, int(config.pre_roll_ms / max(1, config.frame_ms)))
        pre_roll: deque[AudioFrame] = deque(maxlen=pre_roll_frames)
        utterance_frames: list[AudioFrame] = []
        voiced_streak = 0
        silence_ms = 0
        recorded_ms = 0
        started_at: float | None = None

        for frame in self.input_provider.frames():
            voiced = self.vad.is_voiced(frame)

            if started_at is None:
                if voiced:
                    voiced_streak += 1
                    if voiced_streak >= config.speech_start_frames:
                        started_at = frame.timestamp or time()
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
                return self._save_utterance(utterance_frames, started_at)

            if recorded_ms >= int(config.max_utterance_seconds * 1000):
                return self._save_utterance(utterance_frames, started_at)

        if started_at is not None and utterance_frames:
            return self._save_utterance(utterance_frames, started_at)
        return None

    def _save_utterance(self, frames: list[AudioFrame], started_at: float) -> Utterance:
        ended_at = time()
        filename = f"utterance_{utc_compact_timestamp()}_{int(time() * 1000) % 1000000:06d}.wav"
        wav_info = self.recorder.save_frames(frames, filename=filename)
        return Utterance(
            wav_path=wav_info.path,
            started_at=started_at,
            ended_at=ended_at,
            duration_ms=wav_info.duration_ms,
            frame_count=len(frames),
            wav_info=wav_info,
        )
