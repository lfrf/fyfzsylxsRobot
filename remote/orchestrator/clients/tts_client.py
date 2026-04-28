from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote, urljoin

import httpx

from config import settings
from contracts.schemas import TTSResult
from services.robot_media_store import robot_media_store


@dataclass(frozen=True)
class TTSClientResult:
    tts: TTSResult
    source: str
    detail: str | None = None


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
        if not text.strip():
            return TTSClientResult(tts=TTSResult(type="none", audio_url=None, format="wav"), source="empty_text")

        if self.use_mock or not self.base_url:
            return TTSClientResult(tts=self._mock_tts(session_id=session_id, turn_id=turn_id), source="mock")

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
                response = client.post(f"{self.base_url}/tts/synthesize", json=payload)
                response.raise_for_status()
            body = response.json()
            raw_audio_url = body.get("audio_url")
            audio_url = self._resolve_robot_audio_url(
                raw_audio_url=raw_audio_url,
                session_id=session_id,
                turn_id=turn_id,
            )
            return TTSClientResult(
                tts=TTSResult(
                    type=body.get("type") or "audio_url",
                    audio_url=audio_url,
                    format=body.get("format") or "wav",
                    duration_ms=body.get("duration_ms"),
                ),
                source=body.get("source") or "speech_service_tts",
            )
        except Exception as exc:
            return TTSClientResult(
                tts=self._mock_tts(session_id=session_id, turn_id=turn_id),
                source=f"fallback:{type(exc).__name__}",
                detail=str(exc),
            )

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


tts_client = TTSClient()

__all__ = ["TTSClient", "TTSClientResult", "tts_client"]
