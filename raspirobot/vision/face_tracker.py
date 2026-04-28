from dataclasses import dataclass, field
from time import time
from typing import Protocol

from shared.schemas import RobotFaceState


class FaceTracker(Protocol):
    def start(self) -> None:
        ...

    def stop(self) -> None:
        ...

    def get_latest_state(self) -> RobotFaceState:
        ...

    def get_recent_context(self, seconds: float = 5.0) -> list[RobotFaceState]:
        ...

    def is_alive(self) -> bool:
        ...


FaceTrackerProvider = FaceTracker


@dataclass
class MockFaceTracker:
    running: bool = False
    history: list[RobotFaceState] = field(default_factory=list)

    def start(self) -> None:
        self.running = True
        self.history.append(self._new_state())

    def stop(self) -> None:
        self.running = False

    def get_latest_state(self) -> RobotFaceState:
        if not self.history:
            self.history.append(self._new_state())
        return self.history[-1]

    def get_recent_context(self, seconds: float = 5.0) -> list[RobotFaceState]:
        lower_bound = time() - seconds
        return [item for item in self.history if item.timestamp is None or item.timestamp >= lower_bound]

    def is_alive(self) -> bool:
        return self.running

    def _new_state(self) -> RobotFaceState:
        return RobotFaceState(
            timestamp=time(),
            face_detected=False,
            tracking_state="mock",
        )
