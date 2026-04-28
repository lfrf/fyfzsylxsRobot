from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from urllib.parse import quote, urljoin

import httpx

from config import settings
from contracts.schemas import TTSResult
from logging_utils import log_event
from services.robot_media_store import robot_media_store


@dataclass(frozen=True)
class TTSClientResult:
    tts: TTSResult
    source: str
    detail: str | None = None
    latency_ms: float | None = None
    fallback: bool = False
    service_url: str | None = None


class TTSClient:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
        use_mock: bool | None = None,
    ) -> None:
        self.base_url = (base_url if base_url is not None else settings.tts_service_base).strip().rstrip("/")
        self.timeout_seconds = timeout_seconds if timeout_seconds is not None else settings.tts_service_timeout_seconds
        self.use_mock = settings.robot_chat_use_mock_tts if use_mock is None else use_mock

    def synthesize(
        self,
        *,
        text: str,
        session_id: str,
        turn_id: str,
        mode: str,
        speech_style: str,
    ) -> TTSClientResult:
        service_url = f"{self.base_url}/tts/synthesize" if self.base_url else None
        log_event(
            "tts_request_started",
            service_url=service_url,
            text_len=len(text or ""),
            mode=mode,
            speech_style=speech_style,
            mock_enabled=self.use_mock,
        )
        started = perf_counter()
        if not text.strip():
            result = TTSClientResult(
                tts=TTSResult(type="none", audio_url=None, format="wav"),
                source="empty_text",
                latency_ms=round((perf_counter() - started) * 1000, 2),
                fallback=False,
                service_url=service_url,
            )
            self._log_result(result)
            return result

        if self.use_mock or not self.base_url:
            result = TTSClientResult(
                tts=self._mock_tts(session_id=session_id, turn_id=turn_id),
                source="mock",
                latency_ms=round((perf_counter() - started) * 1000, 2),
                fallback=True,
                service_url=service_url,
            )
            self._log_result(result)
            return result

        payload = {
            "session_id": session_id,
            "turn_id": turn_id,
            "text": text,
            "mode": mode,
            "speech_style": speech_style,
            "provider": settings.robot_tts_provider,
        }
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(service_url, json=payload)
                response.raise_for_status()
            body = response.json()
            raw_audio_url = body.get("audio_url")
            audio_url = self._resolve_robot_audio_url(
                raw_audio_url=raw_audio_url,
                session_id=session_id,
                turn_id=turn_id,
            )
            result = TTSClientResult(
                tts=TTSResult(
                    type=body.get("type") or "audio_url",
                    audio_url=audio_url,
                    format=body.get("format") or "wav",
                    duration_ms=body.get("duration_ms"),
                ),
                source=body.get("source") or "speech_service_tts",
                latency_ms=round((perf_counter() - started) * 1000, 2),
                fallback=False,
                service_url=service_url,
            )
            self._log_result(result)
            return result
        except Exception as exc:
            result = TTSClientResult(
                tts=self._mock_tts(session_id=session_id, turn_id=turn_id),
                source=f"fallback:{type(exc).__name__}",
                detail=str(exc),
                latency_ms=round((perf_counter() - started) * 1000, 2),
                fallback=True,
                service_url=service_url,
            )
            self._log_result(result)
            return result

    def _resolve_robot_audio_url(self, *, raw_audio_url: str | None, session_id: str, turn_id: str) -> str | None:
        if not raw_audio_url:
            return None
        if raw_audio_url.startswith("mock://"):
            return raw_audio_url

        if raw_audio_url.startswith("/"):
            upstream_url = urljoin(f"{self.base_url}/", raw_audio_url.lstrip("/"))
        else:
            upstream_url = raw_audio_url

        if not settings.robot_tts_proxy_media:
            return upstream_url

        robot_media_store.register(session_id=session_id, turn_id=turn_id, upstream_url=upstream_url)
        safe_session = quote(session_id, safe="")
        safe_turn = quote(turn_id, safe="")
        return f"/v1/robot/media/tts/{safe_session}/{safe_turn}.wav"

    def _mock_tts(self, *, session_id: str, turn_id: str) -> TTSResult:
        safe_session = quote(session_id, safe="")
        safe_turn = quote(turn_id, safe="")
        return TTSResult(type="audio_url", audio_url=f"mock://tts/{safe_session}/{safe_turn}.wav", format="wav")

    def _log_result(self, result: TTSClientResult) -> None:
        log_event(
            "tts_result",
            audio_url=result.tts.audio_url,
            format=result.tts.format,
            source=result.source,
            latency_ms=result.latency_ms,
            fallback=result.fallback,
        )


tts_client = TTSClient()

__all__ = ["TTSClient", "TTSClientResult", "tts_client"]
