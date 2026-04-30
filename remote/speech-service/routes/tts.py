from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from models import TTSRequest, TTSResponse
from logging_utils import log_context, log_event
from services.tts_service import tts_service


router = APIRouter(prefix="/tts")


@router.post("/synthesize", response_model=TTSResponse)
async def synthesize_tts(request: TTSRequest, http_request: Request) -> TTSResponse:
    log_session_id = http_request.headers.get("x-robot-log-session-id") or request.session_id
    with log_context(
        log_session_id=log_session_id,
        robot_session_id=request.session_id,
        robot_turn_id=request.turn_id,
        component="speech_service_tts",
    ):
        log_event(
            "speech_service_tts_request_received",
            session_id=request.session_id,
            turn_id=request.turn_id,
            text_len=len(request.text or ""),
            mode=request.mode,
            speech_style=request.speech_style,
            provider=request.provider,
        )
        response = tts_service.synthesize(request)
        log_event(
            "speech_service_tts_response_ready",
            session_id=request.session_id,
            turn_id=request.turn_id,
            audio_url=response.audio_url,
            duration_ms=response.duration_ms,
            source=response.source,
            model_ref=response.model_ref,
            device=response.device,
        )
        return response


@router.get("/audio/{session_id}/{turn_id}.wav")
async def get_tts_audio(session_id: str, turn_id: str) -> FileResponse:
    path = tts_service.get_audio_path(session_id=session_id, turn_id=turn_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="TTS audio not found.")
    return FileResponse(path, media_type="audio/wav", filename=f"{turn_id}.wav")
