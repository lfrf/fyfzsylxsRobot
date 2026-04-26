import threading
import time
from collections import deque
from dataclasses import dataclass

from config import settings
from models import TurnTimeWindow, VideoFrame


@dataclass
class WindowSelectionResult:
    video_frames: list[VideoFrame]
    buffer_frame_count: int
    selection_mode: str
    window_started_at_ms: int | None
    window_ended_at_ms: int | None


def _clone_frame_with_timestamp(frame: VideoFrame, timestamp_ms: int) -> VideoFrame:
    if hasattr(frame, "model_copy"):
        return frame.model_copy(update={"timestamp_ms": timestamp_ms})
    return frame.copy(update={"timestamp_ms": timestamp_ms})


def _downsample_evenly(frames: list[VideoFrame], max_count: int) -> list[VideoFrame]:
    if max_count <= 0 or len(frames) <= max_count:
        return frames
    if max_count == 1:
        return [frames[len(frames) // 2]]

    selected: list[VideoFrame] = []
    last_index = len(frames) - 1
    for slot in range(max_count):
        source_index = round((slot * last_index) / (max_count - 1))
        selected.append(frames[source_index])
    return selected


class VideoRingBuffer:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._buffers: dict[str, deque[VideoFrame]] = {}

    def ingest(
        self,
        *,
        session_id: str,
        turn_time_window: TurnTimeWindow | None,
        frames: list[VideoFrame],
    ) -> int:
        if not settings.ring_buffer_enabled:
            return len(frames)

        key = self._key(session_id, turn_time_window)
        now_ms = int(time.time() * 1000)
        with self._lock:
            queue = self._buffers.setdefault(key, deque())
            for frame in frames:
                timestamp_ms = frame.timestamp_ms if frame.timestamp_ms is not None else now_ms
                queue.append(_clone_frame_with_timestamp(frame, timestamp_ms))
            self._trim_locked(queue, now_ms)
            while len(queue) > settings.ring_buffer_max_frames:
                queue.popleft()
            return len(queue)

    def select_window(
        self,
        *,
        session_id: str,
        turn_time_window: TurnTimeWindow | None,
        fallback_frames: list[VideoFrame],
    ) -> WindowSelectionResult:
        if not settings.ring_buffer_enabled:
            selected = _downsample_evenly(fallback_frames, settings.ring_buffer_window_max_frames)
            started_at, ended_at = self._resolve_window_range(turn_time_window, selected, None)
            return WindowSelectionResult(
                video_frames=selected,
                buffer_frame_count=len(selected),
                selection_mode="request_only",
                window_started_at_ms=started_at,
                window_ended_at_ms=ended_at,
            )

        key = self._key(session_id, turn_time_window)
        now_ms = int(time.time() * 1000)
        with self._lock:
            queue = self._buffers.get(key)
            if not queue:
                selected = _downsample_evenly(fallback_frames, settings.ring_buffer_window_max_frames)
                started_at, ended_at = self._resolve_window_range(turn_time_window, selected, now_ms)
                return WindowSelectionResult(
                    video_frames=selected,
                    buffer_frame_count=0,
                    selection_mode="request_only_no_buffer",
                    window_started_at_ms=started_at,
                    window_ended_at_ms=ended_at,
                )

            self._trim_locked(queue, now_ms)
            snapshot = list(queue)

        started_at, ended_at = self._resolve_window_range(turn_time_window, fallback_frames, now_ms)
        selected: list[VideoFrame] = []
        if started_at is not None and ended_at is not None:
            selected = [
                frame
                for frame in snapshot
                if frame.timestamp_ms is not None and started_at <= frame.timestamp_ms <= ended_at
            ]

        selection_mode = "ring_window"
        if not selected:
            selected = fallback_frames
            selection_mode = "request_fallback"
        if not selected:
            selected = snapshot[-settings.ring_buffer_window_max_frames :]
            selection_mode = "ring_tail_fallback"

        selected = _downsample_evenly(selected, settings.ring_buffer_window_max_frames)
        if selected and (started_at is None or ended_at is None):
            timestamps = [frame.timestamp_ms for frame in selected if frame.timestamp_ms is not None]
            if timestamps:
                started_at = min(timestamps)
                ended_at = max(timestamps)

        return WindowSelectionResult(
            video_frames=selected,
            buffer_frame_count=len(snapshot),
            selection_mode=selection_mode,
            window_started_at_ms=started_at,
            window_ended_at_ms=ended_at,
        )

    def _key(self, session_id: str, turn_time_window: TurnTimeWindow | None) -> str:
        stream_id = turn_time_window.stream_id if turn_time_window and turn_time_window.stream_id else "default"
        return f"{session_id}:{stream_id}"

    def _trim_locked(self, queue: deque[VideoFrame], now_ms: int) -> None:
        lower_bound = now_ms - settings.ring_buffer_max_age_ms
        while queue and queue[0].timestamp_ms is not None and queue[0].timestamp_ms < lower_bound:
            queue.popleft()

    def _resolve_window_range(
        self,
        turn_time_window: TurnTimeWindow | None,
        fallback_frames: list[VideoFrame],
        now_ms: int | None,
    ) -> tuple[int | None, int | None]:
        if turn_time_window:
            if (
                turn_time_window.capture_started_at_ms is not None
                and turn_time_window.capture_ended_at_ms is not None
                and turn_time_window.capture_ended_at_ms >= turn_time_window.capture_started_at_ms
            ):
                return turn_time_window.capture_started_at_ms, turn_time_window.capture_ended_at_ms

            if turn_time_window.triggered_at_ms is not None:
                pre_roll = turn_time_window.pre_roll_ms or 0
                post_roll = turn_time_window.post_roll_ms or 0
                return (
                    turn_time_window.triggered_at_ms - pre_roll,
                    turn_time_window.triggered_at_ms + post_roll,
                )

            if (
                turn_time_window.capture_ended_at_ms is not None
                and turn_time_window.window_duration_ms is not None
                and turn_time_window.window_duration_ms >= 0
            ):
                return (
                    turn_time_window.capture_ended_at_ms - turn_time_window.window_duration_ms,
                    turn_time_window.capture_ended_at_ms,
                )

        timestamps = [frame.timestamp_ms for frame in fallback_frames if frame.timestamp_ms is not None]
        if timestamps:
            return min(timestamps), max(timestamps)

        if now_ms is None:
            return None, None

        return now_ms - settings.ring_buffer_window_default_ms, now_ms


video_ring_buffer = VideoRingBuffer()
