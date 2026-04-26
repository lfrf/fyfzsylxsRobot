from dataclasses import dataclass

import httpx

from config import settings
from models import ChatRequest


@dataclass
class EmotionInferenceResult:
    dominant_emotion: str | None
    emotion_tags: list[str]
    confidence: float | None
    source: str
    model_ref: str | None = None


class EmotionClient:
    async def infer_turn(self, request: ChatRequest, canonical_user_text: str | None = None) -> EmotionInferenceResult:
        if settings.emotion_service_enabled:
            try:
                return await self._call_service(request, canonical_user_text)
            except httpx.HTTPError:
                pass

        return self._heuristic_fallback(request)

    async def _call_service(self, request: ChatRequest, canonical_user_text: str | None) -> EmotionInferenceResult:
        payload = {
            "session_id": request.session_id,
            "turn_id": request.turn_id,
            "input_type": request.input_type,
            "canonical_user_text": canonical_user_text,
            "speech_features": (
                request.speech_features.model_dump()
                if request.speech_features and hasattr(request.speech_features, "model_dump")
                else request.speech_features.dict() if request.speech_features
                else None
            ),
            "vision_features": (
                request.vision_features.model_dump()
                if request.vision_features and hasattr(request.vision_features, "model_dump")
                else request.vision_features.dict() if request.vision_features
                else None
            ),
            "turn_time_window": (
                request.turn_time_window.model_dump()
                if request.turn_time_window and hasattr(request.turn_time_window, "model_dump")
                else request.turn_time_window.dict() if request.turn_time_window
                else None
            ),
        }

        async with httpx.AsyncClient(timeout=settings.emotion_service_timeout_seconds) as client:
            response = await client.post(f"{settings.emotion_service_base}/analyze", json=payload)
            response.raise_for_status()

        body = response.json()
        payload_body = body.get("emotion_result") if isinstance(body.get("emotion_result"), dict) else body
        dominant_emotion = _normalize_text(payload_body.get("dominant_emotion"))
        emotion_tags = _normalize_tags(payload_body.get("emotion_tags") or payload_body.get("tags"))
        if dominant_emotion and dominant_emotion not in emotion_tags:
            emotion_tags.insert(0, dominant_emotion)
        if not dominant_emotion and emotion_tags:
            dominant_emotion = emotion_tags[0]

        return EmotionInferenceResult(
            dominant_emotion=dominant_emotion,
            emotion_tags=emotion_tags,
            confidence=_normalize_confidence(payload_body.get("confidence")),
            source=_normalize_text(payload_body.get("source")) or "emotion_service",
            model_ref=_normalize_text(payload_body.get("model_ref")),
        )

    def _heuristic_fallback(self, request: ChatRequest) -> EmotionInferenceResult:
        speech_tags = _normalize_tags(request.speech_features.emotion_tags if request.speech_features else [])
        vision_tags = _normalize_tags(request.vision_features.emotion_tags if request.vision_features else [])

        dominant_emotion: str | None = None
        if speech_tags and vision_tags:
            speech_set = set(speech_tags)
            for tag in vision_tags:
                if tag in speech_set:
                    dominant_emotion = tag
                    break
        if not dominant_emotion and vision_tags:
            dominant_emotion = vision_tags[0]
        if not dominant_emotion and speech_tags:
            dominant_emotion = speech_tags[0]

        merged_tags = _merge_tags(speech_tags, vision_tags)
        if dominant_emotion and dominant_emotion not in merged_tags:
            merged_tags.insert(0, dominant_emotion)

        return EmotionInferenceResult(
            dominant_emotion=dominant_emotion,
            emotion_tags=merged_tags,
            confidence=None,
            source="speech_vision_heuristic",
            model_ref=None,
        )


def _normalize_tags(value) -> list[str]:
    if not isinstance(value, list):
        return []
    normalized: list[str] = []
    for item in value:
        text = _normalize_text(item)
        if text and text not in normalized:
            normalized.append(text)
    return normalized


def _merge_tags(primary: list[str], secondary: list[str]) -> list[str]:
    merged: list[str] = []
    for item in primary + secondary:
        if item not in merged:
            merged.append(item)
    return merged


def _normalize_text(value) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def _normalize_confidence(value) -> float | None:
    if value is None:
        return None
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return None
    if confidence < 0:
        return 0.0
    if confidence > 1:
        return 1.0
    return confidence


emotion_client = EmotionClient()
