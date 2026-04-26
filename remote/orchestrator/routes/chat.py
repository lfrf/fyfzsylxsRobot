from fastapi import APIRouter, HTTPException

from models import ChatRequest, ChatResponse, ErrorResponse
from services.observability import orchestrator_observability
from services.dialog_service import dialog_service

router = APIRouter()


@router.post(
    "/chat",
    response_model=ChatResponse,
    responses={400: {"model": ErrorResponse}},
)
async def chat(request: ChatRequest) -> ChatResponse:
    return await process_chat_request(request)


async def process_chat_request(request: ChatRequest) -> ChatResponse:
    has_text = bool(request.user_text.strip())
    has_audio = bool(request.audio_base64 or request.audio_chunks or request.audio_stream_event)
    if not has_text and not has_audio:
        raise HTTPException(status_code=400, detail="Either user_text or audio input is required.")

    orchestrator_observability.log_chat_request_received(
        request.session_id,
        request.turn_id,
        {
            "input_type": request.input_type,
            "text_source": request.text_source,
            "alignment_mode": request.alignment_mode,
            "avatar_profile_id": request.avatar_profile_id,
            "has_audio": has_audio,
            "has_vision": bool(request.vision_features or request.video_frames or request.video_meta),
            "video_frame_count": len(request.video_frames),
        },
    )
    return await dialog_service.build_reply(request)
