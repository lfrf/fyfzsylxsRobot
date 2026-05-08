from __future__ import annotations

import re
import sys
from pathlib import Path
from time import perf_counter
from uuid import uuid4

import httpx
from fastapi import APIRouter
from pydantic import BaseModel, Field

SHARED_PATH_CANDIDATES = [
    Path("/shared"),
    Path(__file__).resolve().parents[3] / "shared",
]

for candidate in SHARED_PATH_CANDIDATES:
    if candidate.exists() and str(candidate) not in sys.path:
        sys.path.append(str(candidate))

from clients.asr_client import asr_client  # noqa: E402
from clients.tts_client import tts_client  # noqa: E402
from config import settings  # noqa: E402
from contracts.schemas import (  # noqa: E402
    EmotionResult,
    RobotAction,
    RobotChatRequest,
    RobotInput,
    RobotState,
    TTSResult,
    VisionContext,
)
from logging_utils import log_event  # noqa: E402
from services.mode_policy import get_mode_service  # noqa: E402
from services.profile import profile_store, user_profile_service  # noqa: E402
from services.robot_action_service import robot_action_service  # noqa: E402

router = APIRouter(prefix="/v1/robot", tags=["robot-registration"])

USERNAME_PROMPT_TEXT = "\u4f60\u5e0c\u671b\u6211\u600e\u4e48\u79f0\u547c\u4f60\u5462\uff1f"
KNOWN_USER_GREETING_TEMPLATE = "\u4f60\u597d\uff0c{display_name}\uff0c\u6211\u4eec\u5f00\u59cb\u804a\u5929\u5427\u3002"
USERNAME_CONFIRM_TEMPLATE = "\u597d\u7684\uff0c\u6211\u8bb0\u4f4f\u4e86\u3002\u4ee5\u540e\u6211\u5c31\u53eb\u4f60{display_name}\u3002"
USERNAME_NOT_HEARD_TEXT = "\u6211\u521a\u624d\u6ca1\u6709\u542c\u6e05\u4f60\u7684\u79f0\u547c\u3002\u6211\u4eec\u5148\u5f00\u59cb\u804a\u5929\u5427\u3002"


class PrepareUserRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    turn_id: str = Field(default="prepare")
    mode: str = Field(default="care")
    vision_context: VisionContext | None = None
    robot_state: RobotState | None = None
    request_options: dict = Field(default_factory=dict)


class PrepareUserResponse(BaseModel):
    success: bool = True
    session_id: str
    turn_id: str
    face_detected: bool = False
    face_id: str | None = None
    user_id: str | None = None
    display_name: str | None = None
    needs_username_registration: bool = False
    reply_text: str = ""
    tts: TTSResult = Field(default_factory=TTSResult)
    robot_action: RobotAction = Field(default_factory=RobotAction)
    debug: dict = Field(default_factory=dict)


class RegisterUsernameRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    turn_id: str = Field(default="username")
    user_id: str = Field(..., min_length=1)
    mode: str = Field(default="care")
    input: RobotInput
    request_options: dict = Field(default_factory=dict)


class RegisterUsernameResponse(BaseModel):
    success: bool = True
    session_id: str
    turn_id: str
    user_id: str
    display_name: str | None = None
    asr_text: str = ""
    reply_text: str = ""
    tts: TTSResult = Field(default_factory=TTSResult)
    robot_action: RobotAction = Field(default_factory=RobotAction)
    debug: dict = Field(default_factory=dict)


@router.post("/prepare_user", response_model=PrepareUserResponse)
async def prepare_user(request: PrepareUserRequest) -> PrepareUserResponse:
    started = perf_counter()
    trace_id = uuid4().hex
    mode_policy = get_mode_service(request.mode).get_policy()
    face_identity = request.vision_context.face_identity if request.vision_context else None
    face_detected = bool(face_identity and face_identity.face_detected and face_identity.face_id)

    log_event(
        "prepare_user_started",
        trace_id=trace_id,
        session_id=request.session_id,
        turn_id=request.turn_id,
        mode=request.mode,
        face_detected=face_detected,
        face_id=getattr(face_identity, "face_id", None),
    )

    if not face_detected:
        return _prepare_response(
            request=request,
            trace_id=trace_id,
            started=started,
            face_detected=False,
            user_id=None,
            face_id=None,
            display_name=None,
            needs_username_registration=False,
            reply_text="",
            mode_policy=mode_policy,
            reason="no_face",
        )

    face_id = str(face_identity.face_id)
    existing_user_id = profile_store.get_user_id_for_face(face_id)
    if existing_user_id:
        profile = profile_store.ensure_user(existing_user_id, face_id=face_id)
    else:
        profile = profile_store.create_user_for_face(face_id)
    display_name = getattr(profile, "display_name", None)
    needs_username_registration = not bool(getattr(profile, "username_registered_at", None)) or not bool(display_name)
    sync_result = _sync_vision_face_user(
        face_id=face_id,
        user_id=profile.user_id,
        display_name=None if needs_username_registration else display_name,
    )
    reply_text = (
        USERNAME_PROMPT_TEXT
        if needs_username_registration
        else KNOWN_USER_GREETING_TEMPLATE.format(display_name=display_name)
    )

    return _prepare_response(
        request=request,
        trace_id=trace_id,
        started=started,
        face_detected=True,
        user_id=profile.user_id,
        face_id=face_id,
        display_name=display_name,
        needs_username_registration=needs_username_registration,
        reply_text=reply_text,
        mode_policy=mode_policy,
        reason="needs_username" if needs_username_registration else "known_user",
        extra_debug={"vision_sync": sync_result},
    )


@router.post("/register_username", response_model=RegisterUsernameResponse)
async def register_username(request: RegisterUsernameRequest) -> RegisterUsernameResponse:
    started = perf_counter()
    trace_id = uuid4().hex
    mode_policy = get_mode_service(request.mode).get_policy()
    chat_request = RobotChatRequest(
        session_id=request.session_id,
        turn_id=request.turn_id,
        mode=request.mode,
        input=request.input,
        request_options=request.request_options,
    )
    asr_result = asr_client.transcribe(chat_request)
    nickname = _extract_nickname(asr_result.text)

    if nickname:
        profile = user_profile_service.update_display_name(request.user_id, nickname)
        reply_text = USERNAME_CONFIRM_TEMPLATE.format(display_name=profile.display_name)
        display_name = profile.display_name
        sync_results = [
            _sync_vision_face_user(face_id=face_id, user_id=profile.user_id, display_name=profile.display_name)
            for face_id in profile.face_ids
        ]
        success = True
    else:
        reply_text = USERNAME_NOT_HEARD_TEXT
        display_name = None
        sync_results = []
        success = False

    emotion = EmotionResult(label="neutral", confidence=1.0)
    robot_action = robot_action_service.for_chat(mode_policy, emotion)
    tts_result = tts_client.synthesize(
        text=reply_text,
        session_id=request.session_id,
        turn_id=request.turn_id,
        mode=mode_policy.mode_id,
        speech_style=mode_policy.speech_style,
    )
    log_event(
        "register_username_done",
        trace_id=trace_id,
        session_id=request.session_id,
        turn_id=request.turn_id,
        user_id=request.user_id,
        display_name=display_name,
        asr_text=asr_result.text,
        success=success,
    )
    return RegisterUsernameResponse(
        success=success,
        session_id=request.session_id,
        turn_id=request.turn_id,
        user_id=request.user_id,
        display_name=display_name,
        asr_text=asr_result.text,
        reply_text=reply_text,
        tts=tts_result.tts,
        robot_action=robot_action,
        debug={
            "trace_id": trace_id,
            "reason": "registered" if success else "nickname_not_found",
            "latency_ms": round((perf_counter() - started) * 1000, 2),
            "asr_source": asr_result.source,
            "tts_source": tts_result.source,
            "vision_sync": sync_results,
        },
    )


def _prepare_response(
    *,
    request: PrepareUserRequest,
    trace_id: str,
    started: float,
    face_detected: bool,
    user_id: str | None,
    face_id: str | None,
    display_name: str | None,
    needs_username_registration: bool,
    reply_text: str,
    mode_policy,
    reason: str,
    extra_debug: dict | None = None,
) -> PrepareUserResponse:
    emotion = EmotionResult(label="neutral", confidence=1.0)
    robot_action = robot_action_service.for_chat(mode_policy, emotion)
    if reply_text:
        tts_result = tts_client.synthesize(
            text=reply_text,
            session_id=request.session_id,
            turn_id=request.turn_id,
            mode=mode_policy.mode_id,
            speech_style=mode_policy.speech_style,
        )
        tts = tts_result.tts
        tts_source = tts_result.source
    else:
        tts = TTSResult(type="none", audio_url=None, format="wav")
        tts_source = "skipped:empty_prepare_reply"

    log_event(
        "prepare_user_done",
        trace_id=trace_id,
        session_id=request.session_id,
        turn_id=request.turn_id,
        reason=reason,
        face_detected=face_detected,
        face_id=face_id,
        user_id=user_id,
        display_name=display_name,
        needs_username_registration=needs_username_registration,
        reply_text=reply_text,
        tts_audio_url=tts.audio_url,
    )
    return PrepareUserResponse(
        success=True,
        session_id=request.session_id,
        turn_id=request.turn_id,
        face_detected=face_detected,
        face_id=face_id,
        user_id=user_id,
        display_name=display_name,
        needs_username_registration=needs_username_registration,
        reply_text=reply_text,
        tts=tts,
        robot_action=robot_action,
        debug={
            "trace_id": trace_id,
            "reason": reason,
            "latency_ms": round((perf_counter() - started) * 1000, 2),
            "tts_source": tts_source,
            **(extra_debug or {}),
        },
    )


def _sync_vision_face_user(*, face_id: str, user_id: str, display_name: str | None) -> dict:
    if not settings.vision_service_enabled or not settings.vision_service_base:
        return {"success": False, "skipped": True, "reason": "vision_service_disabled"}
    url = f"{settings.vision_service_base.rstrip('/')}/v1/vision/identity/link-user"
    payload = {
        "face_id": face_id,
        "user_id": user_id,
        "display_name": display_name,
    }
    try:
        with httpx.Client(timeout=settings.vision_service_timeout_seconds) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
        body = response.json()
        log_event(
            "vision_face_user_sync_done",
            face_id=face_id,
            user_id=user_id,
            display_name=display_name,
            success=body.get("success"),
            url=url,
        )
        return {"success": bool(body.get("success")), "url": url, "error": body.get("error")}
    except Exception as exc:
        log_event(
            "vision_face_user_sync_failed",
            face_id=face_id,
            user_id=user_id,
            display_name=display_name,
            url=url,
            error=str(exc),
            level="warning",
        )
        return {"success": False, "url": url, "error": str(exc)}


def _extract_nickname(text: str | None) -> str | None:
    normalized = (text or "").strip()
    if not normalized:
        return None
    normalized = normalized.replace("\u3002", " ").replace("\uff0c", " ").replace(",", " ").strip()
    patterns = [
        r"(?:\u53eb\u6211|\u79f0\u547c\u6211|\u4f60\u53ef\u4ee5\u53eb\u6211|\u6211\u7684\u540d\u5b57\u662f|\u6211\u53eb)\s*([\u4e00-\u9fffA-Za-z0-9_-]{1,12})",
        r"^([\u4e00-\u9fffA-Za-z0-9_-]{1,12})$",
        r"([\u4e00-\u9fffA-Za-z0-9_-]{2,12})",
    ]
    ignored = {
        "\u55ef",
        "\u554a",
        "\u54e6",
        "\u597d\u7684",
        "\u53ef\u4ee5",
        "\u5f00\u59cb",
        "\u804a\u5929",
    }
    for pattern in patterns:
        match = re.search(pattern, normalized)
        if not match:
            continue
        candidate = match.group(1).strip()
        if candidate and candidate not in ignored:
            return candidate
    return None
