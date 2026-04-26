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
    ChatRequestSchema,
    ChatResponseSchema,
    EmotionInferenceSchema,
    ErrorResponseSchema,
    MultimodalEvidenceSchema,
    MultimodalResultSchema,
    MultimodalSignalSchema,
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


class ChatRequest(ChatRequestSchema):
    audio_meta: AudioMeta | None = None
    video_frames: list[VideoFrame] = Field(default_factory=list)
    video_meta: VideoMeta | None = None
    speech_features: SpeechFeatures | None = None
    vision_features: VisionFeatures | None = None
    turn_time_window: TurnTimeWindow | None = None


class ContextMessage(BaseModel):
    role: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)
    turn_id: int | None = Field(default=None, ge=1)
    input_mode: str | None = None


class AvatarAction(AvatarActionSchema):
    pass


class AvatarOutput(AvatarOutputSchema):
    pass


class MultimodalSignal(MultimodalSignalSchema):
    pass


class EmotionInference(EmotionInferenceSchema):
    pass


class MultimodalEvidence(MultimodalEvidenceSchema):
    pass


class MultimodalResult(MultimodalResultSchema):
    modalities: list[MultimodalSignal] = Field(default_factory=list)
    evidence: MultimodalEvidence | None = None


class ChatResponse(ChatResponseSchema):
    avatar_action: AvatarAction
    avatar_output: AvatarOutput | None = None
    multimodal_result: MultimodalResult | None = None
    reply_audio_url: str | None = None
    reply_video_url: str | None = None
    reply_video_stream_url: str | None = None
    video_text: str | None = None
    video_is_partial: bool = False


class HealthResponse(BaseModel):
    status: str
    server_time: str
    orchestrator_mode: str
    llm_provider: str
    llm_model: str
    emotion_service_enabled: bool
    emotion_service_base: str | None = None


class ErrorResponse(ErrorResponseSchema):
    pass
