from models import VideoFrame


def select_key_frames(frames: list[VideoFrame], limit: int) -> list[VideoFrame]:
    if limit <= 0 or len(frames) <= limit:
        return frames

    if limit == 1:
        return [frames[len(frames) // 2]]

    last_index = len(frames) - 1
    selected: list[VideoFrame] = []

    for slot in range(limit):
        frame_index = round((slot * last_index) / (limit - 1))
        selected.append(frames[frame_index])

    return selected
