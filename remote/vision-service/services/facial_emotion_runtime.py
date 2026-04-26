import base64
import os
from dataclasses import dataclass
from io import BytesIO

import numpy as np
from PIL import Image

from config import settings
from models import VideoFrame


@dataclass(frozen=True)
class FacialEmotionResult:
    dominant_emotion: str | None
    emotion_tags: list[str]
    confidence: float | None
    source: str
    model_ref: str | None = None


class FacialEmotionRuntime:
    def __init__(self) -> None:
        self._recognizer = None
        self._face_detector = None

    def warmup(self) -> None:
        if not settings.fer_enabled or not settings.fer_warmup_enabled:
            return
        try:
            self._ensure_recognizer()
        except Exception:
            # Keep startup resilient when FER dependencies or model weights are absent.
            pass

    def infer(self, frames: list[VideoFrame]) -> FacialEmotionResult | None:
        if not settings.fer_enabled:
            return None
        if not frames:
            return None

        try:
            recognizer = self._ensure_recognizer()
        except Exception:
            return None

        weighted_scores: dict[str, float] = {}
        sampled_frames = 0
        for frame in frames[: settings.fer_max_frames]:
            if not frame.image_base64:
                continue
            sampled_frames += 1
            image_rgb = _decode_frame_to_rgb(frame.image_base64)
            if image_rgb is None:
                continue

            face_rgb = self._extract_face(image_rgb)
            if face_rgb is None:
                face_rgb = image_rgb

            try:
                raw_label, confidence = self._predict_single(recognizer, face_rgb)
            except Exception:
                # Keep /extract resilient on single-frame FER inference failure.
                continue
            if raw_label is None or confidence is None or confidence < settings.fer_min_confidence:
                continue
            weighted_scores[raw_label] = weighted_scores.get(raw_label, 0.0) + confidence

        if not weighted_scores:
            return None

        dominant_label = max(weighted_scores.items(), key=lambda item: item[1])[0]
        total_weight = sum(weighted_scores.values()) or 1.0
        confidence = max(min(weighted_scores[dominant_label] / total_weight, 1.0), 0.0)
        mapped_tag = _map_face_emotion(dominant_label)
        tags = _dedupe([mapped_tag, f"face_{dominant_label}"])
        return FacialEmotionResult(
            dominant_emotion=mapped_tag,
            emotion_tags=tags,
            confidence=confidence,
            source="fer_hsemotion",
            model_ref=settings.fer_model_name,
        )

    def _ensure_recognizer(self):
        if self._recognizer is not None:
            return self._recognizer
        if settings.fer_provider != "hsemotion":
            raise RuntimeError(f"Unsupported FER_PROVIDER={settings.fer_provider}")
        if settings.fer_force_no_weights_only_load:
            # hsemotion checkpoints require legacy torch.load behavior on torch>=2.6.
            os.environ.setdefault("TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD", "1")

        try:
            from hsemotion.facial_emotions import HSEmotionRecognizer
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("FER requires hsemotion package.") from exc

        self._recognizer = HSEmotionRecognizer(
            model_name=settings.fer_model_name,
            device=settings.fer_device,
        )
        return self._recognizer

    def _predict_single(self, recognizer, face_rgb: np.ndarray) -> tuple[str | None, float | None]:
        label, scores = recognizer.predict_emotions(face_rgb, logits=False)
        normalized_label = _normalize_label(label)
        if not normalized_label:
            return None, None

        confidence = None
        try:
            if isinstance(scores, np.ndarray):
                if scores.size > 0:
                    confidence = float(np.max(scores))
            elif isinstance(scores, dict):
                if scores:
                    confidence = max(float(score) for score in scores.values())
            elif isinstance(scores, (list, tuple)):
                if scores:
                    confidence = max(float(score) for score in scores)
            elif scores is not None:
                confidence = float(scores)
        except (TypeError, ValueError):
            confidence = None
        return normalized_label, confidence

    def _extract_face(self, image_rgb: np.ndarray) -> np.ndarray | None:
        if settings.fer_detector not in {"haar", "haarcascade"}:
            return None
        detector = self._ensure_face_detector()
        if detector is None:
            return None

        try:
            import cv2
        except ImportError:
            return None

        gray = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2GRAY)
        faces = detector.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(48, 48),
        )
        if len(faces) == 0:
            return None

        x, y, w, h = max(faces, key=lambda box: box[2] * box[3])
        x_end = min(x + w, image_rgb.shape[1])
        y_end = min(y + h, image_rgb.shape[0])
        return image_rgb[y:y_end, x:x_end]

    def _ensure_face_detector(self):
        if self._face_detector is not None:
            return self._face_detector
        try:
            import cv2
        except ImportError:
            return None
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        detector = cv2.CascadeClassifier(cascade_path)
        if detector.empty():
            return None
        self._face_detector = detector
        return detector


def _decode_frame_to_rgb(image_base64: str) -> np.ndarray | None:
    try:
        image_bytes = base64.b64decode(image_base64)
        image = Image.open(BytesIO(image_bytes)).convert("RGB")
        return np.asarray(image)
    except Exception:
        return None


def _normalize_label(label) -> str | None:
    if not isinstance(label, str):
        return None
    text = label.strip().lower()
    if not text:
        return None
    return text.replace("-", "_").replace(" ", "_")


def _map_face_emotion(label: str | None) -> str:
    if not label:
        return "neutral"
    if label in {"angry", "anger", "fear", "fearful", "disgust"}:
        return "tense"
    if label in {"sad", "sadness"}:
        return "sad"
    if label in {"happy", "happiness", "surprise", "surprised"}:
        return "calm"
    return "neutral"


def _dedupe(items: list[str]) -> list[str]:
    normalized: list[str] = []
    for item in items:
        text = item.strip()
        if text and text not in normalized:
            normalized.append(text)
    return normalized


facial_emotion_runtime = FacialEmotionRuntime()
