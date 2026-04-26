from datetime import datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel

from config import settings

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    server_time: str
    orchestrator_mode: str
    llm_provider: str
    llm_model: str
    emotion_service_enabled: bool
    emotion_service_base: str | None = None


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        server_time=datetime.now(timezone.utc).isoformat(),
        orchestrator_mode="robotmatch-v1",
        llm_provider=settings.llm_provider,
        llm_model=settings.llm_model,
        emotion_service_enabled=settings.emotion_service_enabled,
        emotion_service_base=settings.emotion_service_base if settings.emotion_service_enabled else None,
    )
