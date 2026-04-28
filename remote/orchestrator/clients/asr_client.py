from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter

import httpx

from config import settings
from contracts.schemas import RobotChatRequest
from logging_utils import log_event


@dataclass(frozen=True)
class ASRResult:
    text: str
    source: str
    confidence: float | None = None
    model_ref: str | None = None
    device: str | None = None
    latency_ms: float | None = None
    fallback: bool = False
    service_url: str | None = None


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
        service_url = f"{self.base_url}/asr/transcribe" if self.base_url else None
        log_event(
            "asr_request_started",
            service_url=service_url,
            session_id=request.session_id,
            turn_id=request.turn_id,
            mock_enabled=self.use_mock,
            audio_base64_len=len(request.input.audio_base64 or ""),
        )
        started = perf_counter()
        if request.input.text_hint and request.input.text_hint.strip():
            result = ASRResult(
                text=request.input.text_hint.strip(),
                source="text_hint",
                confidence=1.0,
                latency_ms=round((perf_counter() - started) * 1000, 2),
                fallback=False,
                service_url=service_url,
            )
            self._log_result(result)
            return result

        if self.use_mock or not self.base_url:
            result = self._mock_result(
                request,
                reason="mock_enabled_or_missing_base",
                latency_ms=round((perf_counter() - started) * 1000, 2),
                service_url=service_url,
            )
            self._log_result(result)
            return result

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
                response = client.post(service_url, json=payload)
                response.raise_for_status()
            body = response.json()
        except Exception as exc:
            result = self._mock_result(
                request,
                reason=f"fallback_after_error:{type(exc).__name__}:{exc}",
                latency_ms=round((perf_counter() - started) * 1000, 2),
                service_url=service_url,
            )
            self._log_result(result)
            return result

        text = str(body.get("transcript_text") or "").strip()
        result = ASRResult(
            text=text or "mock audio received",
            source=body.get("text_source") or "speech_service",
            confidence=body.get("transcript_confidence"),
            model_ref=body.get("model_ref"),
            device=body.get("device"),
            latency_ms=round((perf_counter() - started) * 1000, 2),
            fallback=False,
            service_url=service_url,
        )
        self._log_result(result)
        return result

    def _mock_result(
        self,
        request: RobotChatRequest,
        *,
        reason: str,
        latency_ms: float | None,
        service_url: str | None,
    ) -> ASRResult:
        return ASRResult(
            text=request.input.text_hint or "mock audio received",
            source=reason,
            confidence=0.0,
            latency_ms=latency_ms,
            fallback=True,
            service_url=service_url,
        )

    def _log_result(self, result: ASRResult) -> None:
        log_event(
            "asr_result",
            asr_text=result.text,
            source=result.source,
            confidence=result.confidence,
            latency_ms=result.latency_ms,
            fallback=result.fallback,
        )


asr_client = ASRClient()

__all__ = ["ASRClient", "ASRResult", "asr_client"]
