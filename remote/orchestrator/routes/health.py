from datetime import datetime, timezone

from fastapi import APIRouter

from config import settings
from models import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        server_time=datetime.now(timezone.utc).isoformat(),
        orchestrator_mode="multimodal-audio-alignment-ready",
        llm_provider=settings.llm_provider,
        llm_model=settings.llm_model,
        emotion_service_enabled=settings.emotion_service_enabled,
        emotion_service_base=settings.emotion_service_base if settings.emotion_service_enabled else None,
    )
