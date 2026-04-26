from models import TurnTimeWindow, VideoFrame


def merge_video_window(
    turn_time_window: TurnTimeWindow | None,
    frames: list[VideoFrame],
) -> TurnTimeWindow | None:
    if not turn_time_window or not frames:
        return turn_time_window

    timestamps = [frame.timestamp_ms for frame in frames if frame.timestamp_ms is not None]
    if not timestamps:
        return turn_time_window

    started_at = min(timestamps)
    ended_at = max(timestamps)
    if hasattr(turn_time_window, "model_copy"):
        next_window = turn_time_window.model_copy(deep=True)
    else:
        next_window = turn_time_window.copy(deep=True)
    next_window.video_started_at_ms = started_at
    next_window.video_ended_at_ms = ended_at

    if next_window.capture_started_at_ms is None:
        next_window.capture_started_at_ms = started_at
    if next_window.capture_ended_at_ms is None or ended_at > next_window.capture_ended_at_ms:
        next_window.capture_ended_at_ms = ended_at
    if (
        next_window.capture_started_at_ms is not None
        and next_window.capture_ended_at_ms is not None
        and next_window.capture_ended_at_ms >= next_window.capture_started_at_ms
    ):
        next_window.window_duration_ms = next_window.capture_ended_at_ms - next_window.capture_started_at_ms

    return next_window
