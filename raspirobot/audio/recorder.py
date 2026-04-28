from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from shared.schemas import RobotInput

from .input_provider import AudioFrame
from .wav_utils import WavInfo, write_wav


class AudioRecorder(Protocol):
    def record_turn(self) -> RobotInput:
        ...


@dataclass
class MockAudioRecorder:
    audio_base64: str = "UklGRiQAAABXQVZFZm10IBAAAAABAAEA"
    text_hint: str | None = None

    def record_turn(self) -> RobotInput:
        return RobotInput(
            type="audio_base64",
            audio_base64=self.audio_base64,
            audio_format="wav",
            sample_rate=16000,
            channels=1,
            duration_ms=0,
            text_hint=self.text_hint,
        )


@dataclass
class WavRecorder:
    output_dir: str | Path
    sample_rate: int = 16000
    channels: int = 1
    sample_width: int = 2

    def save_frames(self, frames: list[AudioFrame], *, filename: str) -> WavInfo:
        if not frames:
            raise ValueError("Cannot save an empty utterance.")

        sample_rate = frames[0].sample_rate or self.sample_rate
        channels = frames[0].channels or self.channels
        sample_width = frames[0].sample_width or self.sample_width
        path = Path(self.output_dir) / filename
        return write_wav(
            path,
            [frame.pcm for frame in frames],
            sample_rate=sample_rate,
            channels=channels,
            sample_width=sample_width,
        )
