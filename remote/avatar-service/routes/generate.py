import asyncio
import logging
import math
import wave

from fastapi import APIRouter, BackgroundTasks

from config import settings
from models import GenerateRequest, GenerateResponse
from services.avatar_event_bus import avatar_event_bus
from services.avatar_render_bridge import avatar_render_bridge
from services.expression_generator import expression_generator
from services.motion_generator import motion_generator
from services.soulxflashhead_render_bridge import (
    SoulXFlashHeadRenderRequest,
    soulxflashhead_render_bridge,
)
from services.storage import avatar_storage
from services.tts_runtime import tts_runtime
from services.viseme_generator import viseme_generator

router = APIRouter()
A2F_EVENT_CONTRACT_VERSION = "a2f-ab-v1"
logger = logging.getLogger(__name__)


@router.post("/generate", response_model=GenerateResponse)
async def generate(request: GenerateRequest, background_tasks: BackgroundTasks) -> GenerateResponse:
    stream_id = _resolve_stream_id(request)
    await avatar_event_bus.publish(
        payload={
            "event": "turn_start",
            "contract_version": A2F_EVENT_CONTRACT_VERSION,
            "session_id": request.session_id,
            "turn_id": request.turn_id,
            "stream_id": stream_id,
            "emotion_style": request.emotion_style,
            "renderer_mode": settings.renderer_mode,
        },
        session_id=request.session_id,
        stream_id=stream_id,
    )

    estimated_duration_ms = min(max(len(request.reply_text) * 180, 1200), 8000)
    try:
        render_in_background = False
        reply_audio_url = tts_runtime.synthesize(
            session_id=request.session_id,
            turn_id=request.turn_id,
            text=request.reply_text,
            instruct_text=request.tts_instruct_text,
            speed=request.tts_speed,
            speaker_id=request.tts_speaker_id,
        )
        reply_video_path = None
        reply_video_url = None
        reply_video_stream_url = None
        audio_path = avatar_storage.get_audio_path(session_id=request.session_id, turn_id=request.turn_id)
        estimated_duration_ms, audio_sample_rate_hz = _resolve_audio_meta(
            audio_path,
            fallback_ms=estimated_duration_ms,
        )

        if settings.avatar_renderer_backend == "echomimic_v2" and settings.echomimic_root and reply_audio_url:
            render_fps = 24
            settle_tail_ms = 900
            render_duration_ms = estimated_duration_ms + settle_tail_ms
            render_length = max(60, math.ceil((render_duration_ms / 1000.0) * render_fps) + 6)
            render_request = avatar_render_bridge.build_request(
                session_id=request.session_id,
                turn_id=request.turn_id,
                audio_path=str(audio_path),
                ref_image_path=request.ref_image_path or settings.echomimic_ref_image_path,
                emotion_style=request.emotion_style,
                pose_dir=request.pose_dir or settings.echomimic_pose_dir or None,
                fps=render_fps,
                length=render_length,
            )
            render_result = avatar_render_bridge.render_video(
                render_request,
                workdir=settings.echomimic_root,
                infer_script=settings.echomimic_infer_script,
                timeout_seconds=settings.echomimic_timeout_seconds,
            )
            persisted_video_path = avatar_storage.persist_video(
                session_id=request.session_id,
                turn_id=request.turn_id,
                source_path=render_result.video_path,
            )
            reply_video_path = str(persisted_video_path)
            reply_video_url = f"/media/video/{request.session_id}/{request.turn_id}"
            reply_video_stream_url = _persist_single_chunk_manifest(
                session_id=request.session_id,
                turn_id=request.turn_id,
                chunk_seconds=render_result.duration_ms / 1000.0 if render_result.duration_ms else None,
            )

        if settings.avatar_renderer_backend == "soulxflashhead" and settings.soulx_root and reply_audio_url:
            render_request = soulxflashhead_render_bridge.build_request(
                session_id=request.session_id,
                turn_id=request.turn_id,
                audio_path=str(audio_path),
                ref_image_path=request.ref_image_path or settings.soulx_ref_image_path,
                emotion_style=request.emotion_style,
                fps=settings.soulx_fps,
                chunk_seconds=settings.soulx_chunk_seconds,
                metadata={"stream_id": stream_id},
            )
            if settings.soulx_async_render:
                reply_video_stream_url = _persist_pending_manifest(
                    session_id=request.session_id,
                    turn_id=request.turn_id,
                    chunk_seconds=settings.soulx_chunk_seconds,
                )
                render_in_background = True
                background_tasks.add_task(
                    _render_soulx_video_in_background,
                    request=request,
                    render_request=render_request,
                    stream_id=stream_id,
                )
            else:
                render_result = soulxflashhead_render_bridge.render_video(
                    render_request,
                    workdir=settings.soulx_root,
                    infer_script=settings.soulx_infer_script,
                    timeout_seconds=settings.soulx_timeout_seconds,
                    command_template=settings.soulx_command_template,
                    extra_args=settings.soulx_extra_args,
                )
                persisted_video_path = avatar_storage.persist_video(
                    session_id=request.session_id,
                    turn_id=request.turn_id,
                    source_path=render_result.video_path,
                )
                avatar_storage.persist_video_chunk(
                    session_id=request.session_id,
                    turn_id=request.turn_id,
                    chunk_index=1,
                    source_path=render_result.video_path,
                )
                reply_video_path = str(persisted_video_path)
                reply_video_url = f"/media/video/{request.session_id}/{request.turn_id}"
                reply_video_stream_url = _persist_single_chunk_manifest(
                    session_id=request.session_id,
                    turn_id=request.turn_id,
                    chunk_seconds=settings.soulx_chunk_seconds,
                )

        avatar_output = {
            "contract_version": "v1",
            "renderer_mode": settings.renderer_mode,
            "transport_mode": settings.transport_mode,
            "websocket_endpoint": settings.websocket_endpoint,
            "stream_id": stream_id,
            "sequence_id": request.turn_id,
            "avatar_id": settings.avatar_id,
            "emotion_style": request.emotion_style,
            "audio": {
                "audio_url": reply_audio_url,
                "mime_type": "audio/wav" if reply_audio_url else None,
                "duration_ms": estimated_duration_ms if reply_audio_url else None,
                "sample_rate_hz": audio_sample_rate_hz if reply_audio_url else None,
                "cache_key": f"{request.session_id}:{request.turn_id}:tts" if reply_audio_url else None,
            },
            "viseme_seq": viseme_generator.generate(
                text=request.reply_text,
                duration_ms=estimated_duration_ms,
            ),
            "expression_seq": expression_generator.generate(
                expression=request.avatar_action.facial_expression,
                duration_ms=estimated_duration_ms,
            ),
            "motion_seq": motion_generator.generate(
                motion=request.avatar_action.head_motion,
                duration_ms=estimated_duration_ms,
            ),
        }

        avatar_storage.persist_output(
            session_id=request.session_id,
            turn_id=request.turn_id,
            payload=avatar_output,
        )

        if reply_audio_url:
            await avatar_event_bus.publish(
                payload={
                    "event": "audio_ready",
                    "session_id": request.session_id,
                    "turn_id": request.turn_id,
                    "stream_id": stream_id,
                    "audio": avatar_output["audio"],
                },
                session_id=request.session_id,
                stream_id=stream_id,
            )

        await avatar_event_bus.publish(
            payload={
                "event": "motion_plan",
                "session_id": request.session_id,
                "turn_id": request.turn_id,
                "stream_id": stream_id,
                "viseme_seq": avatar_output["viseme_seq"],
                "expression_seq": avatar_output["expression_seq"],
                "motion_seq": avatar_output["motion_seq"],
            },
            session_id=request.session_id,
            stream_id=stream_id,
        )
        turn_end_status = "rendering" if render_in_background else "ok"
        await avatar_event_bus.publish(
            payload={
                "event": "turn_end",
                "session_id": request.session_id,
                "turn_id": request.turn_id,
                "stream_id": stream_id,
                "status": turn_end_status,
            },
            session_id=request.session_id,
            stream_id=stream_id,
        )
    except Exception as exc:
        await avatar_event_bus.publish(
            payload={
                "event": "turn_error",
                "session_id": request.session_id,
                "turn_id": request.turn_id,
                "stream_id": stream_id,
                "error_code": "AVATAR_GENERATE_FAILED",
                "error_message": str(exc),
            },
            session_id=request.session_id,
            stream_id=stream_id,
        )
        raise

    return GenerateResponse(
        avatar_output=avatar_output,
        reply_audio_url=reply_audio_url,
        reply_video_path=reply_video_path,
        reply_video_url=reply_video_url,
        reply_video_stream_url=reply_video_stream_url,
    )


def _resolve_stream_id(request: GenerateRequest) -> str:
    if request.turn_time_window and request.turn_time_window.stream_id:
        stream_id = request.turn_time_window.stream_id.strip()
        if stream_id:
            return stream_id
    return f"{request.session_id}:default"


def _resolve_audio_meta(audio_path, *, fallback_ms: int) -> tuple[int, int | None]:
    try:
        with wave.open(str(audio_path), "rb") as wav_file:
            sample_rate = wav_file.getframerate()
            frame_count = wav_file.getnframes()
        if sample_rate <= 0:
            return fallback_ms, None
        duration_ms = max(fallback_ms, math.ceil((frame_count / sample_rate) * 1000))
        return duration_ms, sample_rate
    except Exception:
        return fallback_ms, None


def _persist_single_chunk_manifest(*, session_id: str, turn_id: int, chunk_seconds: float | None) -> str:
    manifest_payload = {
        "session_id": session_id,
        "turn_id": turn_id,
        "chunk_seconds": chunk_seconds,
        "complete": True,
        "chunks": [
            {
                "index": 1,
                "url": f"/media/video-chunk/{session_id}/{turn_id}/1",
            }
        ],
    }
    avatar_storage.persist_video_manifest(
        session_id=session_id,
        turn_id=turn_id,
        payload=manifest_payload,
    )
    return f"/media/video-stream/{session_id}/{turn_id}/manifest"


def _persist_pending_manifest(*, session_id: str, turn_id: int, chunk_seconds: float | None) -> str:
    manifest_payload = {
        "session_id": session_id,
        "turn_id": turn_id,
        "chunk_seconds": chunk_seconds,
        "complete": False,
        "chunks": [],
    }
    avatar_storage.persist_video_manifest(
        session_id=session_id,
        turn_id=turn_id,
        payload=manifest_payload,
    )
    return f"/media/video-stream/{session_id}/{turn_id}/manifest"


async def _render_soulx_video_in_background(
    *,
    request: GenerateRequest,
    render_request: SoulXFlashHeadRenderRequest,
    stream_id: str,
) -> None:
    try:
        render_result = await asyncio.to_thread(
            soulxflashhead_render_bridge.render_video,
            render_request,
            workdir=settings.soulx_root,
            infer_script=settings.soulx_infer_script,
            timeout_seconds=settings.soulx_timeout_seconds,
            command_template=settings.soulx_command_template,
            extra_args=settings.soulx_extra_args,
        )
        persisted_video_path = await asyncio.to_thread(
            avatar_storage.persist_video,
            session_id=request.session_id,
            turn_id=request.turn_id,
            source_path=render_result.video_path,
        )
        await asyncio.to_thread(
            avatar_storage.persist_video_chunk,
            session_id=request.session_id,
            turn_id=request.turn_id,
            chunk_index=1,
            source_path=render_result.video_path,
        )
        await asyncio.to_thread(
            _persist_single_chunk_manifest,
            session_id=request.session_id,
            turn_id=request.turn_id,
            chunk_seconds=settings.soulx_chunk_seconds,
        )
        await avatar_event_bus.publish(
            payload={
                "event": "video_ready",
                "session_id": request.session_id,
                "turn_id": request.turn_id,
                "stream_id": stream_id,
                "reply_video_path": str(persisted_video_path),
                "reply_video_url": f"/media/video/{request.session_id}/{request.turn_id}",
                "reply_video_stream_url": f"/media/video-stream/{request.session_id}/{request.turn_id}/manifest",
            },
            session_id=request.session_id,
            stream_id=stream_id,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "SoulX background render failed for session=%s turn=%s",
            request.session_id,
            request.turn_id,
        )
        await asyncio.to_thread(
            avatar_storage.persist_runtime_error,
            session_id=request.session_id,
            turn_id=request.turn_id,
            payload={
                "error_code": "SOULX_RENDER_FAILED",
                "error_message": str(exc),
            },
        )
        await asyncio.to_thread(
            avatar_storage.persist_video_manifest,
            session_id=request.session_id,
            turn_id=request.turn_id,
            payload={
                "session_id": request.session_id,
                "turn_id": request.turn_id,
                "chunk_seconds": settings.soulx_chunk_seconds,
                "complete": True,
                "chunks": [],
            },
        )
        await avatar_event_bus.publish(
            payload={
                "event": "turn_error",
                "session_id": request.session_id,
                "turn_id": request.turn_id,
                "stream_id": stream_id,
                "error_code": "AVATAR_RENDER_FAILED",
                "error_message": str(exc),
            },
            session_id=request.session_id,
            stream_id=stream_id,
        )
