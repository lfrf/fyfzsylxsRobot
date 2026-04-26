from dataclasses import dataclass
from typing import Protocol

from shared.schemas import RobotInput


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

