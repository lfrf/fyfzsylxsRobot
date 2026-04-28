from __future__ import annotations

from dataclasses import dataclass

from .eyes import MockEyesDriver
from .head import MockHeadDriver


@dataclass
class DeviceManager:
    eyes: MockEyesDriver
    head: MockHeadDriver

    @classmethod
    def with_mocks(cls) -> "DeviceManager":
        return cls(eyes=MockEyesDriver(), head=MockHeadDriver())

    def readiness(self) -> dict[str, bool]:
        return {
            "oled": False,
            "servo": False,
            "eyes_mock": True,
            "head_mock": True,
        }
