from dataclasses import dataclass
import logging

import httpx

from config import settings
from models import AvatarAction, AvatarOutput, ChatRequest
from services.tts_style_mapper import TTSRenderPlan

logger = logging.getLogger(__name__)


@dataclass
class AvatarGenerationResult:
    avatar_output: AvatarOutput
    reply_audio_url: str | None
    reply_video_url: str | None
    reply_video_stream_url: str | None


class AvatarClient:
    async def generate(
        self,
        *,
        request: ChatRequest,
        reply_text: str,
        emotion_style: str,
        avatar_action: AvatarAction,
        tts_plan: TTSRenderPlan | None = None,
    ) -> AvatarGenerationResult:
        if getattr(settings, "avatar_service_enabled", False):
            try:
                return await self._call_service(
                    request=request,
                    reply_text=reply_text,
                    emotion_style=emotion_style,
                    avatar_action=avatar_action,
                    tts_plan=tts_plan,
                )
            except httpx.HTTPStatusError as exc:
                response_text = ""
                try:
                    response_text = exc.response.text[:600]
                except Exception:  # noqa: BLE001
                    response_text = "<unreadable>"
                logger.warning(
                    "avatar-service returned HTTP %s; detail=%s",
                    exc.response.status_code,
                    response_text,
                )
            except httpx.HTTPError as exc:
                logger.warning("avatar-service request failed: %s", exc)

        return self._build_fallback(
            request=request,
            reply_text=reply_text,
            emotion_style=emotion_style,
            avatar_action=avatar_action,
        )

    async def _call_service(
        self,
        *,
        request: ChatRequest,
        reply_text: str,
        emotion_style: str,
        avatar_action: AvatarAction,
        tts_plan: TTSRenderPlan | None = None,
    ) -> AvatarGenerationResult:
        tts_instruct_text = _non_empty_string(tts_plan.tts_instruct_text if tts_plan else None)
        tts_speaker_id = _non_empty_string(tts_plan.tts_speaker_id if tts_plan else None)
        tts_speed = _positive_float(tts_plan.tts_speed if tts_plan else None)

        payload = {
            "session_id": request.session_id,
            "turn_id": request.turn_id,
            "reply_text": reply_text,
            "emotion_style": emotion_style,
            "tts_instruct_text": tts_instruct_text,
            "tts_speed": tts_speed,
            "tts_speaker_id": tts_speaker_id,
            "ref_image_path": self._resolve_ref_image_path(request),
            "avatar_action": avatar_action.model_dump() if hasattr(avatar_action, "model_dump") else avatar_action.dict(),
            "turn_time_window": (
                request.turn_time_window.model_dump()
                if request.turn_time_window and hasattr(request.turn_time_window, "model_dump")
                else request.turn_time_window.dict() if request.turn_time_window
                else None
            ),
        }

        timeout_seconds = getattr(settings, "avatar_service_timeout_seconds", 20)
        service_base = getattr(settings, "avatar_service_base", "http://127.0.0.1:19300")
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.post(f"{service_base}/generate", json=payload)
            response.raise_for_status()

        body = response.json()
        return AvatarGenerationResult(
            avatar_output=AvatarOutput(**body["avatar_output"]),
            reply_audio_url=body.get("reply_audio_url"),
            reply_video_url=body.get("reply_video_url"),
            reply_video_stream_url=body.get("reply_video_stream_url"),
        )

    def _build_fallback(
        self,
        *,
        request: ChatRequest,
        reply_text: str,
        emotion_style: str,
        avatar_action: AvatarAction,
    ) -> AvatarGenerationResult:
        estimated_duration_ms = min(max(len(reply_text) * 180, 1200), 8000)

        avatar_output = AvatarOutput(
            contract_version="v1",
            renderer_mode="parameterized_2d",
            transport_mode="http_poll",
            websocket_endpoint="/ws/avatar",
            stream_id=request.turn_time_window.stream_id if request.turn_time_window else None,
            sequence_id=request.turn_id,
            avatar_id="default-2d",
            emotion_style=emotion_style,
            audio={
                "audio_url": None,
                "mime_type": None,
                "duration_ms": None,
                "cache_key": None,
            },
            viseme_seq=[
                {"start_ms": 0, "end_ms": estimated_duration_ms // 3, "label": "a", "weight": 0.55},
                {
                    "start_ms": estimated_duration_ms // 3,
                    "end_ms": (estimated_duration_ms * 2) // 3,
                    "label": "e",
                    "weight": 0.5,
                },
                {"start_ms": (estimated_duration_ms * 2) // 3, "end_ms": estimated_duration_ms, "label": "sil", "weight": 0.45},
            ],
            expression_seq=[
                {
                    "start_ms": 0,
                    "end_ms": estimated_duration_ms,
                    "expression": avatar_action.facial_expression,
                    "intensity": 0.72,
                }
            ],
            motion_seq=[
                {
                    "start_ms": 0,
                    "end_ms": estimated_duration_ms,
                    "motion": avatar_action.head_motion,
                    "intensity": 0.6,
                }
            ],
        )
        return AvatarGenerationResult(
            avatar_output=avatar_output,
            reply_audio_url=None,
            reply_video_url=None,
            reply_video_stream_url=None,
        )

    def _resolve_ref_image_path(self, request: ChatRequest) -> str | None:
        direct_path = _non_empty_string(getattr(request, "avatar_ref_image_path", None))
        if direct_path:
            return direct_path

        profile_id = _non_empty_string(getattr(request, "avatar_profile_id", None))
        if profile_id:
            profile_map = getattr(settings, "avatar_profile_ref_image_map", {})
            mapped = _non_empty_string(profile_map.get(profile_id))
            if mapped:
                return mapped

        default_profile_id = _non_empty_string(getattr(settings, "avatar_default_profile_id", None))
        if default_profile_id:
            profile_map = getattr(settings, "avatar_profile_ref_image_map", {})
            mapped_default = _non_empty_string(profile_map.get(default_profile_id))
            if mapped_default:
                return mapped_default
        return None


avatar_client = AvatarClient()


def _non_empty_string(value: str | None) -> str | None:
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed or None


def _positive_float(value: float | None) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed <= 0.0:
        return None
    return parsed
