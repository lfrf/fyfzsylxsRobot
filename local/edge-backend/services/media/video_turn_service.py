from dataclasses import dataclass

from config import settings
from models import TurnTimeWindow, VideoFrame, VideoMeta, VisionFeatures
from services.media.frame_selector import select_key_frames
from services.media.media_package_builder import merge_video_window


@dataclass
class VideoTurnProcessResult:
    video_frames: list[VideoFrame]
    video_meta: VideoMeta | None
    vision_features: VisionFeatures | None
    alignment_mode: str | None
    turn_time_window: TurnTimeWindow | None


class VideoTurnService:
    def process(
        self,
        *,
        video_frames: list[VideoFrame],
        video_meta: VideoMeta | None,
        turn_time_window: TurnTimeWindow | None,
        primary_input_type: str,
    ) -> VideoTurnProcessResult:
        if not video_frames and not video_meta:
            return VideoTurnProcessResult(
                video_frames=[],
                video_meta=None,
                vision_features=None,
                alignment_mode=None,
                turn_time_window=turn_time_window,
            )

        selected_frames = select_key_frames(video_frames, settings.local_video_frame_limit)

        if video_meta:
            if hasattr(video_meta, "model_copy"):
                normalized_meta = video_meta.model_copy(deep=True)
            else:
                normalized_meta = video_meta.copy(deep=True)
        else:
            normalized_meta = VideoMeta()
        normalized_meta.source = normalized_meta.source or "browser_camera"
        normalized_meta.keyframe_strategy = normalized_meta.keyframe_strategy or "even_sampling"
        normalized_meta.frame_count = video_meta.frame_count if video_meta and video_meta.frame_count else len(video_frames)
        normalized_meta.sampled_frame_count = len(selected_frames)

        updated_window = merge_video_window(turn_time_window, selected_frames)

        if primary_input_type == "audio":
            alignment_mode = "video_audio"
        else:
            alignment_mode = "video_text"

        return VideoTurnProcessResult(
            video_frames=selected_frames,
            video_meta=normalized_meta,
            vision_features=None,
            alignment_mode=alignment_mode,
            turn_time_window=updated_window,
        )


video_turn_service = VideoTurnService()
