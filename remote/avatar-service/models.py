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

from contracts.schemas import AvatarActionSchema, AvatarOutputSchema, TurnTimeWindowSchema  # noqa: E402


class AvatarAction(AvatarActionSchema):
    pass


class AvatarOutput(AvatarOutputSchema):
    pass


class TurnTimeWindow(TurnTimeWindowSchema):
    pass


class GenerateRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    turn_id: int = Field(..., ge=1)
    reply_text: str = Field(..., min_length=1)
    emotion_style: str = Field(default="supportive")
    tts_instruct_text: str | None = Field(default=None)
    tts_speed: float | None = Field(default=None, gt=0.0)
    tts_speaker_id: str | None = Field(default=None)
    ref_image_path: str | None = Field(default=None)
    pose_dir: str | None = Field(default=None)
    avatar_action: AvatarAction
    turn_time_window: TurnTimeWindow | None = None


class GenerateResponse(BaseModel):
    avatar_output: AvatarOutput
    reply_audio_url: str | None = None
    reply_video_path: str | None = None
    reply_video_url: str | None = None
    reply_video_stream_url: str | None = None


class HealthResponse(BaseModel):
    status: str
    avatar_id: str
    renderer_mode: str
    tts_mode: str
    tts_model: str
    tts_device: str
    tts_speaker_id: str
