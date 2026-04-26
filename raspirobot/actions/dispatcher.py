from dataclasses import dataclass
from typing import Protocol

from shared.schemas import RobotAction, TTSResult

from raspirobot.audio import AudioPlayer, MockAudioPlayer
from raspirobot.hardware import EyesDriver, HeadDriver, MockEyesDriver, MockHeadDriver


class RobotActionDispatcher(Protocol):
    def dispatch(self, action: RobotAction, tts: TTSResult | None = None) -> None:
        ...


@dataclass
class DefaultRobotActionDispatcher:
    eyes: EyesDriver
    head: HeadDriver
    audio: AudioPlayer

    @classmethod
    def with_mocks(cls) -> "DefaultRobotActionDispatcher":
        return cls(
            eyes=MockEyesDriver(),
            head=MockHeadDriver(),
            audio=MockAudioPlayer(),
        )

    def dispatch(self, action: RobotAction, tts: TTSResult | None = None) -> None:
        self.eyes.set_expression(action.expression)
        self.head.set_motion(action.motion)
        if action.head_target:
            self.head.set_target(
                action.head_target.get("pan"),
                action.head_target.get("tilt"),
            )
        if tts:
            self.audio.play_url(tts.audio_url)
