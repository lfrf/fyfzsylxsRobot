from fastapi import APIRouter

from config import settings
from models import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        avatar_id=settings.avatar_id,
        renderer_mode=settings.renderer_mode,
        tts_mode=settings.tts_mode,
        tts_model=settings.tts_model,
        tts_device=settings.tts_device,
        tts_speaker_id=settings.tts_speaker_id,
    )
