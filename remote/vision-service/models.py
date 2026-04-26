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

from contracts.schemas import TurnTimeWindowSchema, VideoFrameSchema, VideoMetaSchema, VisionFeaturesSchema  # noqa: E402


class VideoFrame(VideoFrameSchema):
    pass


class VideoMeta(VideoMetaSchema):
    pass


class VisionFeatures(VisionFeaturesSchema):
    pass


class TurnTimeWindow(TurnTimeWindowSchema):
    pass


class ExtractRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    turn_id: int = Field(..., ge=1)
    input_type: str = Field(default="text")
    video_frames: list[VideoFrame] = Field(default_factory=list)
    video_meta: VideoMeta | None = None
    turn_time_window: TurnTimeWindow | None = None


class ExtractResponse(BaseModel):
    vision_features: VisionFeatures | None = None
    video_meta: VideoMeta | None = None
    processed_frame_count: int = Field(default=0, ge=0)
    extractor_mode: str


class HealthResponse(BaseModel):
    status: str
    extractor_mode: str
    vision_model: str
    vision_device: str
    frame_input_mode: str
    vision_dtype: str
    ring_buffer_enabled: bool
    ring_buffer_max_frames: int
    ring_buffer_max_age_ms: int
    ring_buffer_window_default_ms: int
    ring_buffer_window_max_frames: int
    fer_enabled: bool
    fer_provider: str
    fer_model_name: str
    fer_device: str
