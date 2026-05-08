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

    def query_latest_frames(
        self,
        *,
        session_id: str,
        stream_id: str,
        window_ms: int,
        max_frames: int,
        min_timestamp_ms: int | None = None,
    ) -> list[VideoFrameItem]:
        session_key = str(session_id)
        stream_key = str(stream_id)
        window_ms = max(0, int(window_ms))
        max_frames = max(1, int(max_frames))

        with self._lock:
            frames = [
                frame
                for (stored_session_id, _turn_id, stored_stream_id), bucket in self._frames.items()
                if stored_session_id == session_key and stored_stream_id == stream_key
                for frame in bucket
            ]

        if not frames:
            return []

        frames.sort(key=lambda frame: frame.timestamp_ms)
        latest_ts = frames[-1].timestamp_ms
        if window_ms > 0:
            cutoff = latest_ts - window_ms
            frames = [frame for frame in frames if frame.timestamp_ms >= cutoff]
        if min_timestamp_ms is not None:
            min_timestamp_ms = max(0, int(min_timestamp_ms))
            frames = [frame for frame in frames if frame.timestamp_ms >= min_timestamp_ms]

        if len(frames) <= max_frames:
            return frames

        if max_frames == 1:
            return [frames[-1]]

        # Uniform sampling keeps coverage across the recent window instead of
        # returning only adjacent frames that may share the same blur/pose.
        last_index = len(frames) - 1
        indexes = [round(index * last_index / (max_frames - 1)) for index in range(max_frames)]
        return [frames[index] for index in indexes]


video_buffer = VideoBuffer()
