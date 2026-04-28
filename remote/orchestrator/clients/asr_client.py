from __future__ import annotations

from dataclasses import dataclass

import httpx

from config import settings
from contracts.schemas import RobotChatRequest


@dataclass(frozen=True)
class ASRResult:
    text: str
    source: str
    confidence: float | None = None
    model_ref: str | None = None
    device: str | None = None


class ASRClient:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
        use_mock: bool | None = None,
    ) -> None:
        self.base_url = (base_url if base_url is not None else settings.speech_service_base).strip().rstrip("/")
        self.timeout_seconds = timeout_seconds if timeout_seconds is not None else settings.speech_service_timeout_seconds
        self.use_mock = settings.robot_chat_use_mock_asr if use_mock is None else use_mock

    def transcribe(self, request: RobotChatRequest) -> ASRResult:
        if request.input.text_hint and request.input.text_hint.strip():
            return ASRResult(text=request.input.text_hint.strip(), source="text_hint", confidence=1.0)

        if self.use_mock or not self.base_url:
            return self._mock_result(request, reason="mock_enabled_or_missing_base")

        payload = {
            "session_id": request.session_id,
            "turn_id": request.turn_id,
            "audio_base64": request.input.audio_base64,
            "audio_format": request.input.audio_format,
            "sample_rate": request.input.sample_rate,
            "channels": request.input.channels,
            "duration_ms": request.input.duration_ms,
        }
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(f"{self.base_url}/asr/transcribe", json=payload)
                response.raise_for_status()
            body = response.json()
        except Exception as exc:
            return self._mock_result(request, reason=f"fallback_after_error:{type(exc).__name__}:{exc}")

        text = str(body.get("transcript_text") or "").strip()
        return ASRResult(
            text=text or "mock audio received",
            source=body.get("text_source") or "speech_service",
            confidence=body.get("transcript_confidence"),
            model_ref=body.get("model_ref"),
            device=body.get("device"),
        )

    def _mock_result(self, request: RobotChatRequest, *, reason: str) -> ASRResult:
        return ASRResult(
            text=request.input.text_hint or "mock audio received",
            source=reason,
            confidence=0.0,
        )


asr_client = ASRClient()

__all__ = ["ASRClient", "ASRResult", "asr_client"]
