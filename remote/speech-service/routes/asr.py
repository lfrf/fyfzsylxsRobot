from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from models import ASRRequest, TranscribeResponse
from logging_utils import log_context, log_event
from services.asr_service import asr_service


router = APIRouter(prefix="/asr")


@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe_asr(request: ASRRequest, http_request: Request) -> TranscribeResponse:
    log_session_id = http_request.headers.get("x-robot-log-session-id") or request.session_id
    with log_context(
        log_session_id=log_session_id,
        robot_session_id=request.session_id,
        robot_turn_id=request.turn_id,
        component="speech_service_asr",
    ):
        log_event(
            "speech_service_asr_request_received",
            session_id=request.session_id,
            turn_id=request.turn_id,
            has_audio_base64=bool(request.audio_base64),
            audio_base64_len=len(request.audio_base64 or ""),
            has_text_hint=bool(request.text_hint and request.text_hint.strip()),
            sample_rate=request.sample_rate,
            channels=request.channels,
        )
        if not request.audio_base64 and not (request.text_hint and request.text_hint.strip()):
            raise HTTPException(status_code=400, detail="ASR requires audio_base64 or text_hint.")
        response = asr_service.transcribe(request)
        log_event(
            "speech_service_asr_response_ready",
            session_id=request.session_id,
            turn_id=request.turn_id,
            transcript_text=response.transcript_text,
            text_source=response.text_source,
            confidence=response.transcript_confidence,
            model_ref=response.model_ref,
            device=response.device,
        )
        return response
