from dataclasses import dataclass
from pathlib import Path

from config import settings


@dataclass(frozen=True)
class SpeechEmotionResult:
    dominant_emotion: str | None
    emotion_tags: list[str]
    confidence: float | None
    source: str
    model_ref: str | None = None


class SpeechEmotionRuntime:
    def __init__(self) -> None:
        self._model = None
        self._backend = None

    def warmup(self) -> None:
        if not settings.ser_enabled or not settings.ser_warmup_enabled:
            return
        try:
            self._ensure_model()
        except Exception:
            # Keep speech service startup resilient on cold environments.
            pass

    def infer(self, *, audio_path: Path) -> SpeechEmotionResult | None:
        if not settings.ser_enabled:
            return None
        if not audio_path.exists():
            return None

        try:
            model = self._ensure_model()
            if self._backend == "wav2vec2_superb_er":
                return self._infer_with_wav2vec2(model, audio_path)
            return self._infer_with_emotion2vec(model, audio_path)
        except Exception:
            return None

    def _ensure_model(self):
        if self._model is not None:
            return self._model

        provider = settings.ser_provider
        if provider in {"wav2vec2_superb_er", "wav2vec2"}:
            self._model = self._ensure_wav2vec2_model()
            self._backend = "wav2vec2_superb_er"
            return self._model

        self._model = self._ensure_emotion2vec_model()
        self._backend = "emotion2vec_plus_base"
        return self._model

    def _ensure_emotion2vec_model(self):
        try:
            from funasr import AutoModel
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("SER requires funasr for emotion2vec_plus inference.") from exc

        model_ref = settings.ser_model
        model_path = Path(model_ref)
        model_kwargs = {
            "model": str(model_path) if model_path.exists() else model_ref,
            "disable_update": True,
        }
        if not model_path.exists():
            model_kwargs["hub"] = settings.ser_hub
        if settings.ser_device:
            model_kwargs["device"] = settings.ser_device
        return AutoModel(**model_kwargs)

    def _ensure_wav2vec2_model(self):
        try:
            from transformers import pipeline
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("SER wav2vec2 backend requires transformers.") from exc

        model_ref = settings.ser_model or "superb/wav2vec2-base-superb-er"
        model_path = Path(model_ref)
        local_files_only = model_path.exists()
        device = -1
        if settings.ser_device.startswith("cuda"):
            device = _resolve_cuda_index(settings.ser_device)

        return pipeline(
            "audio-classification",
            model=model_ref,
            local_files_only=local_files_only,
            device=device,
            top_k=settings.ser_top_k,
        )

    def _infer_with_emotion2vec(self, model, audio_path: Path) -> SpeechEmotionResult | None:
        try:
            payload = model.generate(
                str(audio_path),
                granularity="utterance",
                extract_embedding=False,
            )
        except TypeError:
            payload = model.generate(
                input=str(audio_path),
                granularity="utterance",
                extract_embedding=False,
            )

        labels, scores = _extract_labels_and_scores(payload)
        if not labels or not scores:
            return None

        best_index = max(range(len(scores)), key=lambda index: scores[index])
        confidence = max(min(float(scores[best_index]), 1.0), 0.0)
        if confidence < settings.ser_min_confidence:
            return None

        raw_label = _normalize_label(labels[best_index])
        mapped_tag = _map_speech_emotion(raw_label)
        tags = [mapped_tag]
        if raw_label:
            tags.append(f"ser_{raw_label}")

        return SpeechEmotionResult(
            dominant_emotion=mapped_tag,
            emotion_tags=_dedupe(tags),
            confidence=confidence,
            source="ser_emotion2vec_plus",
            model_ref=settings.ser_model,
        )

    def _infer_with_wav2vec2(self, model, audio_path: Path) -> SpeechEmotionResult | None:
        payload = model(str(audio_path))
        if not isinstance(payload, list) or not payload:
            return None

        top = payload[0]
        raw_label = _normalize_label(top.get("label"))
        confidence = _normalize_confidence(top.get("score"))
        if confidence is None or confidence < settings.ser_min_confidence:
            return None

        mapped_tag = _map_speech_emotion(raw_label)
        tags = [mapped_tag]
        if raw_label:
            tags.append(f"ser_{raw_label}")
        return SpeechEmotionResult(
            dominant_emotion=mapped_tag,
            emotion_tags=_dedupe(tags),
            confidence=confidence,
            source="ser_wav2vec2_superb_er",
            model_ref=settings.ser_model,
        )


def _extract_labels_and_scores(payload) -> tuple[list[str], list[float]]:
    if isinstance(payload, dict):
        payload = [payload]
    if not isinstance(payload, list) or not payload:
        return [], []

    first = payload[0]
    if not isinstance(first, dict):
        return [], []

    labels = first.get("labels") or first.get("label") or []
    scores = first.get("scores") or first.get("score") or []

    if isinstance(labels, str):
        labels = [labels]
    if isinstance(scores, (int, float)):
        scores = [scores]

    normalized_labels = [str(label) for label in labels]
    normalized_scores = []
    for score in scores:
        try:
            normalized_scores.append(float(score))
        except (TypeError, ValueError):
            normalized_scores.append(0.0)

    pair_length = min(len(normalized_labels), len(normalized_scores))
    return normalized_labels[:pair_length], normalized_scores[:pair_length]


def _map_speech_emotion(label: str | None) -> str:
    if not label:
        return "steady"

    normalized = label.lower()
    if normalized in {"angry", "anger", "frustrated", "frustration", "annoyed"}:
        return "agitated"
    if normalized in {"happy", "happiness", "excited", "surprised", "surprise"}:
        return "energized"
    if normalized in {"sad", "sadness", "fear", "fearful", "disgust", "depressed"}:
        return "fatigued"
    if normalized in {"neutral", "calm"}:
        return "calm"
    return "steady"


def _normalize_label(label) -> str | None:
    if not isinstance(label, str):
        return None
    normalized = label.strip().lower()
    if not normalized:
        return None
    normalized = normalized.replace("-", "_").replace(" ", "_")
    if "/" in normalized:
        normalized = normalized.split("/")[-1]
    return normalized


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


def _resolve_cuda_index(device_name: str) -> int:
    if ":" not in device_name:
        return 0
    index_raw = device_name.split(":", maxsplit=1)[1]
    try:
        return int(index_raw)
    except ValueError:
        return 0


def _dedupe(items: list[str]) -> list[str]:
    deduped: list[str] = []
    for item in items:
        text = item.strip()
        if text and text not in deduped:
            deduped.append(text)
    return deduped


speech_emotion_runtime = SpeechEmotionRuntime()
