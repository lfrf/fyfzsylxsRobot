from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from models import TTSRequest, TTSResponse
from services.tts_service import tts_service


router = APIRouter(prefix="/tts")


@router.post("/synthesize", response_model=TTSResponse)
async def synthesize_tts(request: TTSRequest) -> TTSResponse:
    return tts_service.synthesize(request)


@router.get("/audio/{session_id}/{turn_id}.wav")
async def get_tts_audio(session_id: str, turn_id: str) -> FileResponse:
    path = tts_service.get_audio_path(session_id=session_id, turn_id=turn_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="TTS audio not found.")
    return FileResponse(path, media_type="audio/wav", filename=f"{turn_id}.wav")
