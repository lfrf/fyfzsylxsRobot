from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class CameraProvider(Protocol):
    def start(self) -> None:
        ...

    def stop(self) -> None:
        ...

    def get_latest_frame(self) -> bytes | None:
        ...


@dataclass
class MockCameraProvider:
    running: bool = False

    def start(self) -> None:
        self.running = True

    def stop(self) -> None:
        self.running = False

    def get_latest_frame(self) -> bytes | None:
        return None
