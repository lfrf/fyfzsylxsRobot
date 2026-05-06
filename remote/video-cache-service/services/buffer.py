from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from threading import Lock
from typing import Any


@dataclass(slots=True)
class VideoFrameItem:
    session_id: str
    turn_id: str | int
    stream_id: str
    frame_id: int
    timestamp_ms: int
    width: int
    height: int
    mime_type: str
    image_base64: str


class VideoBuffer:
    def __init__(self, max_frames: int = 300) -> None:
        self._max_frames = max_frames
        self._lock = Lock()
        self._frames: dict[tuple[str, str | int, str], deque[VideoFrameItem]] = defaultdict(deque)

    def clear(self) -> None:
        with self._lock:
            self._frames.clear()

    def append_many(self, items: list[dict[str, Any]]) -> int:
        appended = 0
        with self._lock:
            for raw in items:
                item = VideoFrameItem(
                    session_id=str(raw["session_id"]),
                    turn_id=raw["turn_id"],
                    stream_id=str(raw.get("stream_id", "video-001")),
                    frame_id=int(raw["frame_id"]),
                    timestamp_ms=int(raw["timestamp_ms"]),
                    width=int(raw["width"]),
                    height=int(raw["height"]),
                    mime_type=str(raw.get("mime_type", "image/jpeg")),
                    image_base64=str(raw["image_base64"]),
                )
                key = (item.session_id, item.turn_id, item.stream_id)
                bucket = self._frames[key]
                bucket.append(item)
                while len(bucket) > self._max_frames:
                    bucket.popleft()
                appended += 1
        return appended

    def list_keys(self) -> list[tuple[str, str | int, str]]:
        with self._lock:
            return list(self._frames.keys())

    def query_frames(self, *, session_id: str, turn_id: str | int, stream_id: str) -> list[VideoFrameItem]:
        key = (str(session_id), turn_id, str(stream_id))
        with self._lock:
            return list(self._frames.get(key, deque()))


video_buffer = VideoBuffer()
