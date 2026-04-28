from dataclasses import dataclass
from typing import Protocol

from shared.schemas import RobotAction, TTSResult

from raspirobot.audio import AudioOutputProvider, MockAudioPlayer
from raspirobot.hardware import EyesDriver, HeadDriver, MockEyesDriver, MockHeadDriver

from .action_mapping import normalize_action


class RobotActionDispatcher(Protocol):
    def dispatch(self, action: RobotAction, tts: TTSResult | None = None) -> None:
        ...


@dataclass
class DefaultRobotActionDispatcher:
    eyes: EyesDriver
    head: HeadDriver
    audio: AudioOutputProvider | MockAudioPlayer | None = None
    remote_base_url: str | None = None

    @classmethod
    def with_mocks(cls) -> "DefaultRobotActionDispatcher":
        return cls(
            eyes=MockEyesDriver(),
            head=MockHeadDriver(),
            audio=MockAudioPlayer(),
        )

    def dispatch(self, action: RobotAction, tts: TTSResult | None = None) -> None:
        normalized = normalize_action(action)
        self.eyes.set_expression(normalized.expression)
        if hasattr(self.head, "play_motion"):
            self.head.play_motion(normalized.motion)
        else:
            self.head.set_motion(normalized.motion)

        if normalized.head_target:
            pan = normalized.head_target.get("pan")
            tilt = normalized.head_target.get("tilt")
            if hasattr(self.head, "set_pose"):
                self.head.set_pose(pan, tilt)
            else:
                self.head.set_target(pan, tilt)

        if tts and self.audio is not None:
            if hasattr(self.audio, "play_audio_url"):
                self.audio.play_audio_url(tts.audio_url, base_url=self.remote_base_url)
            else:
                self.audio.play_url(tts.audio_url)
