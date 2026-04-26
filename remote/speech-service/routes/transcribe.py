from fastapi import APIRouter, HTTPException

from models import TranscribeRequest, TranscribeResponse
from services.asr_runtime import speech_runtime

router = APIRouter()


@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe(request: TranscribeRequest) -> TranscribeResponse:
    stream_event = (request.audio_stream_event or "").strip().lower()
    if stream_event and stream_event not in {"append", "commit", "clear"}:
        raise HTTPException(status_code=400, detail="Unsupported audio_stream_event.")

    has_audio_payload = bool(request.audio_base64 or request.audio_chunks)
    has_text_hint = bool(request.user_text.strip() or request.client_asr_text)
    if not has_audio_payload and not has_text_hint and stream_event not in {"clear", "commit"}:
        raise HTTPException(status_code=400, detail="Speech service requires audio or transcript hints.")

    if stream_event and hasattr(request, "model_copy"):
        request = request.model_copy(update={"audio_stream_event": stream_event})
    elif stream_event:
        request = request.copy(update={"audio_stream_event": stream_event})
    return speech_runtime.transcribe(request)
