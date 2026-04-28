from __future__ import annotations

from models import ASRRequest, TranscribeRequest, TranscribeResponse
from services.asr_runtime import speech_runtime


class ASRService:
    def transcribe(self, request: ASRRequest) -> TranscribeResponse:
        transcribe_request = TranscribeRequest(
            session_id=request.session_id,
            turn_id=request.turn_id,
            user_text=request.text_hint or "",
            audio_base64=request.audio_base64,
            audio_format=request.audio_format or "wav",
            audio_duration_ms=request.duration_ms,
            audio_sample_rate_hz=request.sample_rate,
            audio_channels=request.channels,
        )
        return speech_runtime.transcribe(transcribe_request)


asr_service = ASRService()

__all__ = ["ASRService", "asr_service"]
