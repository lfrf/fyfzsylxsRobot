from dataclasses import dataclass
from typing import Protocol

from shared.logging_utils import log_event


class HeadDriver(Protocol):
    def play_motion(self, motion: str) -> None:
        ...

    def set_pose(self, pan: float | None, tilt: float | None) -> None:
        ...

    def set_motion(self, motion: str) -> None:
        ...

    def set_target(self, pan: float | None, tilt: float | None) -> None:
        ...


@dataclass
class MockHeadDriver:
    last_motion: str = "none"
    last_pan: float | None = None
    last_tilt: float | None = None

    def play_motion(self, motion: str) -> None:
        self.set_motion(motion)

    def set_pose(self, pan: float | None, tilt: float | None) -> None:
        self.set_target(pan, tilt)

    def set_motion(self, motion: str) -> None:
        self.last_motion = motion or "none"
        log_event(
            "hardware_head_motion_set",
            provider="mock",
            motion=self.last_motion,
        )

    def set_target(self, pan: float | None, tilt: float | None) -> None:
        self.last_pan = pan
        self.last_tilt = tilt
        log_event(
            "hardware_head_pose_set",
            provider="mock",
            pan=pan,
            tilt=tilt,
        )
