from fastapi import APIRouter

from config import settings
from models import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        asr_provider=settings.asr_provider,
        asr_model=settings.asr_model,
        asr_device=settings.asr_device,
        ser_enabled=settings.ser_enabled,
        ser_provider=settings.ser_provider,
        ser_model=settings.ser_model,
        ser_device=settings.ser_device,
    )
