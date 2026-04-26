from dataclasses import dataclass
from typing import Protocol

from shared.schemas import VisionContext

from .face_tracker import FaceTracker, MockFaceTracker


class VisionContextProvider(Protocol):
    def get_context(self, seconds: float = 5.0) -> VisionContext:
        ...


@dataclass
class MockVisionContextProvider:
    face_tracker: FaceTracker | None = None

    def __post_init__(self) -> None:
        if self.face_tracker is None:
            self.face_tracker = MockFaceTracker()

    def get_context(self, seconds: float = 5.0) -> VisionContext:
        assert self.face_tracker is not None
        latest = self.face_tracker.get_latest_state()
        return VisionContext(
            source="mock",
            latest=latest,
            recent=self.face_tracker.get_recent_context(seconds=seconds),
            image_frames=[],
        )

