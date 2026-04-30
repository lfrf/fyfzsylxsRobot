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

from contracts.schemas import AudioMetaSchema, SpeechFeaturesSchema, TurnTimeWindowSchema  # noqa: E402


class AudioMeta(AudioMetaSchema):
    pass


class AudioChunk(BaseModel):
    chunk_id: str | None = None
    sequence_id: int | None = Field(default=None, ge=0)
    audio_base64: str | None = None
    audio_format: str | None = None
    audio_duration_ms: int | None = Field(default=None, ge=0)
    audio_sample_rate_hz: int | None = Field(default=None, ge=1)
    audio_channels: int | None = Field(default=None, ge=1)


class SpeechFeatures(SpeechFeaturesSchema):
    pass


class TurnTimeWindow(TurnTimeWindowSchema):
    pass


class TranscribeRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    turn_id: int | str = Field(...)
    user_text: str = Field(default="")
    client_asr_text: str | None = None
    client_asr_source: str | None = None
    audio_base64: str | None = None
    audio_format: str | None = None
    audio_duration_ms: int | None = Field(default=None, ge=0)
    audio_sample_rate_hz: int | None = Field(default=None, ge=1)
    audio_channels: int | None = Field(default=None, ge=1)
    audio_stream_id: str | None = None
    audio_stream_event: str | None = None
    audio_stream_sequence_id: int | None = Field(default=None, ge=0)
    audio_chunks: list[AudioChunk] = Field(default_factory=list)
    audio_meta: AudioMeta | None = None
    turn_time_window: TurnTimeWindow | None = None


class TranscribeResponse(BaseModel):
    transcript_text: str
    text_source: str
    transcript_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    audio_meta: AudioMeta | None = None
    speech_features: SpeechFeatures | None = None
    model_ref: str | None = None
    device: str | None = None


class ASRRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    turn_id: str = Field(..., min_length=1)
    audio_base64: str | None = None
    audio_format: str | None = Field(default="wav")
    sample_rate: int | None = Field(default=None, ge=1)
    channels: int | None = Field(default=None, ge=1)
    duration_ms: int | None = Field(default=None, ge=0)
    text_hint: str | None = None


class TTSRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    turn_id: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1)
    mode: str = Field(default="care")
    speech_style: str = Field(default="natural_warm")
    provider: str | None = None
    speaker_id: str | None = None
    speed: float | None = Field(default=None, gt=0)


class TTSResponse(BaseModel):
    type: str = Field(default="audio_url")
    audio_url: str | None = None
    format: str = Field(default="wav")
    duration_ms: int | None = Field(default=None, ge=0)
    sample_rate: int | None = Field(default=None, ge=1)
    source: str = Field(default="speech_service_tts")
    model_ref: str | None = None
    device: str | None = None


class HealthResponse(BaseModel):
    status: str
    asr_provider: str
    asr_model: str
    asr_device: str
    ser_enabled: bool
    ser_provider: str
    ser_model: str
    ser_device: str
    tts_provider: str | None = None
    tts_model: str | None = None
    tts_device: str | None = None
