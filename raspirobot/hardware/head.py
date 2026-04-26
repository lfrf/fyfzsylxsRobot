from dataclasses import dataclass
from typing import Protocol


class HeadDriver(Protocol):
    def set_motion(self, motion: str) -> None:
        ...

    def set_target(self, pan: float | None, tilt: float | None) -> None:
        ...


@dataclass
class MockHeadDriver:
    last_motion: str = "none"
    last_pan: float | None = None
    last_tilt: float | None = None

    def set_motion(self, motion: str) -> None:
        self.last_motion = motion or "none"

    def set_target(self, pan: float | None, tilt: float | None) -> None:
        self.last_pan = pan
        self.last_tilt = tilt

