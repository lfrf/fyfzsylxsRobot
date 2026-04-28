from __future__ import annotations

from fastapi import APIRouter, HTTPException

from models import ASRRequest, TranscribeResponse
from services.asr_service import asr_service


router = APIRouter(prefix="/asr")


@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe_asr(request: ASRRequest) -> TranscribeResponse:
    if not request.audio_base64 and not (request.text_hint and request.text_hint.strip()):
        raise HTTPException(status_code=400, detail="ASR requires audio_base64 or text_hint.")
    return asr_service.transcribe(request)
