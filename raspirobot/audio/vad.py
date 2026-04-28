from __future__ import annotations

import audioop
from dataclasses import dataclass

from .input_provider import AudioFrame


@dataclass(frozen=True)
class EnergyVADConfig:
    rms_threshold: float = 500.0
    speech_start_frames: int = 3
    silence_timeout_ms: int = 900
    max_utterance_seconds: float = 15.0
    pre_roll_ms: int = 300
    frame_ms: int = 30


class EnergyVAD:
    def __init__(self, config: EnergyVADConfig | None = None) -> None:
        self.config = config or EnergyVADConfig()

    def rms(self, frame: AudioFrame) -> float:
        if not frame.pcm:
            return 0.0
        return float(audioop.rms(frame.pcm, frame.sample_width))

    def is_voiced(self, frame: AudioFrame) -> bool:
        return self.rms(frame) >= self.config.rms_threshold
