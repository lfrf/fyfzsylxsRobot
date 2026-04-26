import time
from uuid import uuid4

from fastapi import APIRouter, HTTPException

from models import ChatRequest, ChatResponse, ErrorResponse
from services.input_preprocessor import normalize_chat_request
from services.observability import edge_observability
from services.orchestrator_client import RemoteServiceError, orchestrator_client
from services.session_service import session_service

router = APIRouter()


@router.post(
    "/chat",
    response_model=ChatResponse,
    responses={400: {"model": ErrorResponse}, 502: {"model": ErrorResponse}, 504: {"model": ErrorResponse}},
)
async def chat(request: ChatRequest) -> ChatResponse:
    request_id = uuid4().hex[:12]
    started_at = time.perf_counter()
    session_id = session_service.ensure_session(request.session_id)
    turn_id = session_service.ensure_turn(session_id, request.turn_id)
    edge_observability.log_chat_request_received(
        request_id,
        {
            "session_id": session_id,
            "turn_id": turn_id,
            "input_type": request.input_type,
            "avatar_profile_id": request.avatar_profile_id,
            "has_audio": bool(request.audio_base64),
            "has_video": bool(request.video_frames or request.video_meta),
            "has_turn_time_window": bool(request.turn_time_window),
            "user_text_length": len((request.user_text or "").strip()),
        },
    )

    try:
        remote_request = normalize_chat_request(
            request=request,
            session_id=session_id,
            turn_id=turn_id,
            request_id=request_id,
        )
    except ValueError as exc:
        edge_observability.log_chat_error(
            request_id,
            latency_ms=int((time.perf_counter() - started_at) * 1000),
            detail=str(exc),
            status_code=400,
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    edge_observability.log_chat_request_prepared(
        request_id,
        {
            "session_id": remote_request.session_id,
            "turn_id": remote_request.turn_id,
            "input_type": remote_request.input_type,
            "text_source": remote_request.text_source,
            "alignment_mode": remote_request.alignment_mode,
            "avatar_profile_id": remote_request.avatar_profile_id,
            "has_audio": bool(remote_request.audio_base64),
            "has_video": bool(remote_request.video_frames or remote_request.video_meta),
            "client_asr_text": remote_request.client_asr_text,
            "resolved_user_text": remote_request.user_text,
            "turn_window_id": (
                remote_request.turn_time_window.window_id if remote_request.turn_time_window else None
            ),
            "video_frame_count": len(remote_request.video_frames),
            "speech_tags": (
                remote_request.speech_features.emotion_tags if remote_request.speech_features else []
            ),
        },
    )

    try:
        response = await orchestrator_client.send_chat(remote_request, request_id=request_id)
    except RemoteServiceError as exc:
        edge_observability.log_chat_error(
            request_id,
            latency_ms=int((time.perf_counter() - started_at) * 1000),
            detail=exc.detail,
            status_code=exc.status_code,
        )
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except Exception as exc:
        edge_observability.log_chat_error(
            request_id,
            latency_ms=int((time.perf_counter() - started_at) * 1000),
            detail=f"Unexpected local processing error: {exc}",
            status_code=500,
        )
        raise HTTPException(status_code=500, detail="Local edge-backend processing failed.") from exc

    if hasattr(response, "model_copy"):
        final_response = response.model_copy(update={"input_mode": remote_request.input_type})
    else:
        final_response = response.copy(update={"input_mode": remote_request.input_type})

    edge_observability.log_chat_response(
        request_id,
        latency_ms=int((time.perf_counter() - started_at) * 1000),
        payload={
            "session_id": remote_request.session_id,
            "turn_id": remote_request.turn_id,
            "server_status": final_response.server_status,
            "response_source": final_response.response_source,
            "alignment_mode": final_response.alignment_mode,
            "reply_text_preview": final_response.reply_text[:200],
        },
    )
    return final_response
