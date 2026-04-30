from __future__ import annotations

import json
from time import perf_counter
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from shared.schemas import (
    EmotionResult,
    ModeInfo,
    ModeSwitchResult,
    RobotAction,
    RobotChatRequest,
    RobotChatResponse,
    TTSResult,
)

from raspirobot.config import load_settings
from shared.logging_utils import log_event


class RemoteClientProtocol(Protocol):
    def chat_turn(self, request: RobotChatRequest) -> RobotChatResponse:
        ...


class RemoteClientError(RuntimeError):
    pass


class RemoteClient:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        endpoint: str | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        settings = load_settings()
        self.base_url = (base_url or settings.remote_base_url).rstrip("/")
        self.endpoint = endpoint or settings.chat_endpoint
        self.timeout_seconds = timeout_seconds or settings.request_timeout_seconds

    @property
    def url(self) -> str:
        return urljoin(f"{self.base_url}/", self.endpoint.lstrip("/"))

    def resolve_url(self, maybe_relative_url: str | None) -> str | None:
        if not maybe_relative_url:
            return None
        if maybe_relative_url.startswith("/"):
            return urljoin(f"{self.base_url}/", maybe_relative_url.lstrip("/"))
        return maybe_relative_url

    def build_payload(self, request: RobotChatRequest) -> dict[str, Any]:
        if hasattr(request, "model_dump"):
            return request.model_dump()
        return request.dict()

    def chat_turn(self, request: RobotChatRequest) -> RobotChatResponse:
        payload = self.build_payload(request)
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        http_request = Request(
            self.url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )

        log_event(
            "remote_request_started",
            url=self.url,
            session_id=request.session_id,
            turn_id=request.turn_id,
            timeout_seconds=self.timeout_seconds,
            audio_base64_len=len(request.input.audio_base64 or ""),
        )
        started = perf_counter()
        try:
            with urlopen(http_request, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
                status = getattr(response, "status", None)
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            log_event(
                "remote_request_failed",
                url=self.url,
                session_id=request.session_id,
                turn_id=request.turn_id,
                status=exc.code,
                latency_ms=round((perf_counter() - started) * 1000, 2),
                error=detail[:300],
                level="error",
            )
            raise RemoteClientError(f"Robot chat endpoint returned HTTP {exc.code}: {detail}") from exc
        except URLError as exc:
            log_event(
                "remote_request_failed",
                url=self.url,
                session_id=request.session_id,
                turn_id=request.turn_id,
                latency_ms=round((perf_counter() - started) * 1000, 2),
                error=str(exc.reason),
                level="error",
            )
            raise RemoteClientError(f"Robot chat endpoint is unavailable: {exc.reason}") from exc
        except TimeoutError as exc:
            log_event(
                "remote_request_failed",
                url=self.url,
                session_id=request.session_id,
                turn_id=request.turn_id,
                latency_ms=round((perf_counter() - started) * 1000, 2),
                error="timeout",
                level="error",
            )
            raise RemoteClientError("Robot chat endpoint timed out.") from exc

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RemoteClientError(f"Robot chat endpoint returned invalid JSON: {raw[:200]}") from exc

        try:
            if hasattr(RobotChatResponse, "model_validate"):
                parsed = RobotChatResponse.model_validate(data)
            else:
                parsed = RobotChatResponse.parse_obj(data)
        except Exception as exc:
            raise RemoteClientError(f"Robot chat endpoint response does not match RobotChatResponse: {exc}") from exc
        log_event(
            "remote_request_succeeded",
            url=self.url,
            session_id=request.session_id,
            turn_id=request.turn_id,
            status=status,
            latency_ms=round((perf_counter() - started) * 1000, 2),
        )
        return parsed

    def send_chat_turn(self, request: RobotChatRequest) -> RobotChatResponse:
        return self.chat_turn(request)


class MockRemoteClient:
    def chat_turn(self, request: RobotChatRequest) -> RobotChatResponse:
        mode = build_mode_info(request.mode)
        speech_style = {
            "care": "care_gentle",
            "accompany": "natural_warm",
            "learning": "learning_focused",
            "game": "game_playful",
        }.get(mode.mode_id, "natural_warm")
        return RobotChatResponse(
            success=True,
            session_id=request.session_id,
            turn_id=request.turn_id,
            mode=mode,
            mode_switch=ModeSwitchResult(
                switched=False,
                from_mode=request.mode,
                to_mode=request.mode,
            ),
            mode_changed=False,
            active_rag_namespace=mode.rag_namespace,
            asr_text=request.input.text_hint or "mock audio received",
            reply_text="这是机器人远端接口的 mock 回复。",
            emotion=EmotionResult(label="neutral"),
            tts=TTSResult(type="audio_url", audio_url=None, format="wav"),
            robot_action=RobotAction(
                expression="neutral",
                motion="none",
                speech_style=speech_style,
            ),
            debug={"source": "MockRemoteClient"},
        )

    def send_chat_turn(self, request: RobotChatRequest) -> RobotChatResponse:
        return self.chat_turn(request)


def build_mode_info(mode_id: str) -> ModeInfo:
    mode_id = _normalize_mode(mode_id)
    presets = {
        "care": ModeInfo(
            mode_id="care",
            display_name="关怀模式",
            prompt_policy="care_gentle",
            rag_namespace="care",
            action_style="calm_supportive",
        ),
        "accompany": ModeInfo(
            mode_id="accompany",
            display_name="陪伴模式",
            prompt_policy="accompany_warm",
            rag_namespace="general",
            action_style="neutral_warm",
        ),
        "learning": ModeInfo(
            mode_id="learning",
            display_name="学习模式",
            prompt_policy="learning_focused",
            rag_namespace="learning",
            action_style="focused_encouraging",
        ),
        "game": ModeInfo(
            mode_id="game",
            display_name="游戏模式",
            prompt_policy="game_playful",
            rag_namespace="game",
            action_style="playful_warm",
        ),
    }
    return presets.get(mode_id, presets["care"])


def _normalize_mode(mode_id: str | None) -> str:
    aliases = {
        "care": "care",
        "elderly": "care",
        "accompany": "accompany",
        "normal": "accompany",
        "learning": "learning",
        "student": "learning",
        "game": "game",
        "child": "game",
    }
    return aliases.get((mode_id or "").strip().lower(), "care")


__all__ = [
    "MockRemoteClient",
    "RemoteClient",
    "RemoteClientError",
    "RemoteClientProtocol",
    "build_mode_info",
]
