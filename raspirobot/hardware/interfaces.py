from __future__ import annotations

from typing import Protocol


class EyesDriver(Protocol):
    def set_expression(self, expression: str) -> None:
        ...


class HeadDriver(Protocol):
    def play_motion(self, motion: str) -> None:
        ...

    def set_pose(self, pan: float | None, tilt: float | None) -> None:
        ...
