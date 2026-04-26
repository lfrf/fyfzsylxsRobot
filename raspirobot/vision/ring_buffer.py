from collections import deque
from dataclasses import dataclass, field
from time import time

from shared.schemas import RobotFaceState


@dataclass
class VisionRingBuffer:
    max_seconds: float = 10.0
    _items: deque[RobotFaceState] = field(default_factory=deque)

    def append(self, item: RobotFaceState) -> None:
        self._items.append(item)
        self._trim()

    def get_latest(self) -> RobotFaceState | None:
        self._trim()
        if not self._items:
            return None
        return self._items[-1]

    def get_recent(self, seconds: float = 5.0) -> list[RobotFaceState]:
        self._trim()
        lower_bound = time() - seconds
        return [item for item in self._items if item.timestamp is None or item.timestamp >= lower_bound]

    def _trim(self) -> None:
        lower_bound = time() - self.max_seconds
        while self._items and self._items[0].timestamp is not None and self._items[0].timestamp < lower_bound:
            self._items.popleft()

