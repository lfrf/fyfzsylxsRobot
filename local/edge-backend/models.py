import sys
from pathlib import Path

from pydantic import BaseModel, Field

SHARED_PATH_CANDIDATES = [
    Path("/shared"),
    Path(__file__).resolve().parents[2] / "shared" if len(Path(__file__).resolve().parents) > 2 else None,
]

for candidate in SHARED_PATH_CANDIDATES:
    if candidate and candidate.exists() and str(candidate) not in sys.path:
        sys.path.append(str(candidate))

from contracts.schemas import (  # noqa: E402
    AudioMetaSchema,
    AvatarActionSchema,
    AvatarOutputSchema,
    ChatResponseSchema,
    ErrorResponseSchema,
    SpeechFeaturesSchema,
    TurnTimeWindowSchema,
    VideoFrameSchema,
    VideoMetaSchema,
    VisionFeaturesSchema,
)


class AudioMeta(AudioMetaSchema):
    pass


class SpeechFeatures(SpeechFeaturesSchema):
    pass


class VideoFrame(VideoFrameSchema):
    pass


class VideoMeta(VideoMetaSchema):
    pass


class VisionFeatures(VisionFeaturesSchema):
    pass


class TurnTimeWindow(TurnTimeWindowSchema):
    pass


class ChatRequest(BaseModel):
    session_id: str | None = Field(default=None)
    turn_id: int | None = Field(default=None, ge=1)
    user_text: str | None = Field(default=None)
    input_type: str = Field(default="text")
    client_ts: int | None = None
    text_source: str | None = None
    client_asr_text: str | None = None
    client_asr_source: str | None = None
    audio_base64: str | None = None
    audio_format: str | None = None
    audio_duration_ms: int | None = Field(default=None, ge=0)
    audio_sample_rate_hz: int | None = Field(default=None, ge=1)
    audio_channels: int | None = Field(default=None, ge=1)
    audio_meta: AudioMeta | None = None
    video_frames: list[VideoFrame] = Field(default_factory=list)
    video_meta: VideoMeta | None = None
    speech_features: SpeechFeatures | None = None
    vision_features: VisionFeatures | None = None
    turn_time_window: TurnTimeWindow | None = None
    alignment_mode: str | None = None
    avatar_profile_id: str | None = None
    avatar_ref_image_path: str | None = None


class RemoteChatRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    turn_id: int = Field(..., ge=1)
    user_text: str = Field(default="")
    input_type: str = Field(default="text")
    client_ts: int | None = None
    text_source: str | None = None
    client_asr_text: str | None = None
    client_asr_source: str | None = None
    audio_base64: str | None = None
    audio_format: str | None = None
    audio_duration_ms: int | None = Field(default=None, ge=0)
    audio_sample_rate_hz: int | None = Field(default=None, ge=1)
    audio_channels: int | None = Field(default=None, ge=1)
    audio_meta: AudioMeta | None = None
    video_frames: list[VideoFrame] = Field(default_factory=list)
    video_meta: VideoMeta | None = None
    speech_features: SpeechFeatures | None = None
    vision_features: VisionFeatures | None = None
    turn_time_window: TurnTimeWindow | None = None
    alignment_mode: str | None = None
    avatar_profile_id: str | None = None
    avatar_ref_image_path: str | None = None


class AvatarAction(AvatarActionSchema):
    pass


class AvatarOutput(AvatarOutputSchema):
    pass


class ChatResponse(ChatResponseSchema):
    avatar_action: AvatarAction
    avatar_output: AvatarOutput | None = None


class ErrorResponse(ErrorResponseSchema):
    pass


class HealthResponse(BaseModel):
    status: str
    cloud_api_base: str
    cloud_ws_chat_endpoint: str | None = None
    remote_transport: str
    request_timeout_seconds: float
