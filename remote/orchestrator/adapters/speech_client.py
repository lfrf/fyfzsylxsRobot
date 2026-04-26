from dataclasses import dataclass

import httpx

from config import settings
from models import AudioMeta, ChatRequest, SpeechFeatures


@dataclass
class SpeechAnalysisResult:
    transcript_text: str
    text_source: str
    transcript_confidence: float | None
    audio_meta: AudioMeta | None
    speech_features: SpeechFeatures | None
    model_ref: str | None = None
    device: str | None = None


class SpeechClient:
    async def analyze_turn(self, request: ChatRequest) -> SpeechAnalysisResult:
        has_audio_payload = bool(request.audio_base64 or request.audio_chunks or request.audio_stream_event)
        if settings.speech_service_enabled and has_audio_payload:
            try:
                return await self._call_service(request)
            except httpx.HTTPError:
                pass

        fallback_text = (request.user_text or "").strip()
        if not fallback_text:
            fallback_text = (request.client_asr_text or "").strip()

        if not fallback_text and has_audio_payload:
            fallback_text = "Audio input received from the remote speech fallback."

        return SpeechAnalysisResult(
            transcript_text=fallback_text,
            text_source=request.text_source or request.client_asr_source or "speech_fallback",
            transcript_confidence=request.speech_features.transcript_confidence if request.speech_features else None,
            audio_meta=request.audio_meta,
            speech_features=request.speech_features,
        )

    async def _call_service(self, request: ChatRequest) -> SpeechAnalysisResult:
        payload = {
            "session_id": request.session_id,
            "turn_id": request.turn_id,
            "user_text": request.user_text,
            "client_asr_text": request.client_asr_text,
            "client_asr_source": request.client_asr_source,
            "audio_base64": request.audio_base64,
            "audio_format": request.audio_format,
            "audio_duration_ms": request.audio_duration_ms,
            "audio_sample_rate_hz": request.audio_sample_rate_hz,
            "audio_channels": request.audio_channels,
            "audio_stream_id": request.audio_stream_id,
            "audio_stream_event": request.audio_stream_event,
            "audio_stream_sequence_id": request.audio_stream_sequence_id,
            "audio_chunks": [
                chunk.model_dump() if hasattr(chunk, "model_dump") else chunk.dict()
                for chunk in request.audio_chunks
            ],
            "audio_meta": (
                request.audio_meta.model_dump() if request.audio_meta and hasattr(request.audio_meta, "model_dump")
                else request.audio_meta.dict() if request.audio_meta
                else None
            ),
            "turn_time_window": (
                request.turn_time_window.model_dump()
                if request.turn_time_window and hasattr(request.turn_time_window, "model_dump")
                else request.turn_time_window.dict() if request.turn_time_window
                else None
            ),
        }

        async with httpx.AsyncClient(timeout=settings.speech_service_timeout_seconds) as client:
            response = await client.post(f"{settings.speech_service_base}/transcribe", json=payload)
            response.raise_for_status()

        body = response.json()
        return SpeechAnalysisResult(
            transcript_text=body.get("transcript_text", ""),
            text_source=body.get("text_source", "remote_speech_service"),
            transcript_confidence=body.get("transcript_confidence"),
            audio_meta=AudioMeta(**body["audio_meta"]) if body.get("audio_meta") else request.audio_meta,
            speech_features=SpeechFeatures(**body["speech_features"]) if body.get("speech_features") else request.speech_features,
            model_ref=body.get("model_ref"),
            device=body.get("device"),
        )


speech_client = SpeechClient()
