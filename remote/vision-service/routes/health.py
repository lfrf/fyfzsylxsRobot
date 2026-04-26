from fastapi import APIRouter

from config import settings
from models import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        extractor_mode=settings.extractor_mode,
        vision_model=settings.vision_model,
        vision_device=settings.vision_device,
        frame_input_mode=settings.frame_input_mode,
        vision_dtype=settings.vision_dtype,
        ring_buffer_enabled=settings.ring_buffer_enabled,
        ring_buffer_max_frames=settings.ring_buffer_max_frames,
        ring_buffer_max_age_ms=settings.ring_buffer_max_age_ms,
        ring_buffer_window_default_ms=settings.ring_buffer_window_default_ms,
        ring_buffer_window_max_frames=settings.ring_buffer_window_max_frames,
        fer_enabled=settings.fer_enabled,
        fer_provider=settings.fer_provider,
        fer_model_name=settings.fer_model_name,
        fer_device=settings.fer_device,
    )
