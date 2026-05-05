from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from typing import Any

from config import settings


@dataclass(slots=True)
class FaceEmbedding:
    embedding: list[float]
    bbox: dict[str, Any] | None = None
    confidence: float | None = None
    source: str = "mock"
    frame_id: str | None = None
    embedding_model: str | None = None


def _normalize(values: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in values))
    if norm <= 0:
        return [0.0 for _ in values]
    return [value / norm for value in values]


class FaceEmbeddingRuntime:
    def __init__(self, provider: str | None = None) -> None:
        self.provider = (provider or settings.face_recognition_provider or "mock").strip().lower()
        self._insightface_app = None

    def extract(
        self,
        *,
        image_bytes: bytes,
        frame_id: str | None = None,
        width: int | None = None,
        height: int | None = None,
    ) -> list[FaceEmbedding]:
        if not image_bytes and not frame_id:
            return []
        if self.provider == "mock":
            return [self._mock_embedding(image_bytes=image_bytes, frame_id=frame_id)]
        if self.provider == "insightface":
            return self._insightface_embeddings(
                image_bytes=image_bytes,
                frame_id=frame_id,
                width=width,
                height=height,
            )
        raise RuntimeError(f"Unsupported face recognition provider: {self.provider}")

    def _mock_embedding(self, *, image_bytes: bytes, frame_id: str | None) -> FaceEmbedding:
        seed = image_bytes if image_bytes else (frame_id or "mock-face").encode("utf-8")
        digest = hashlib.sha256(seed).digest() + hashlib.sha256(seed + b":robotmatch").digest()
        values = [((byte / 255.0) * 2.0) - 1.0 for byte in digest[:32]]
        return FaceEmbedding(
            embedding=_normalize(values),
            bbox={"x": 0.25, "y": 0.18, "w": 0.5, "h": 0.58, "unit": "normalized"},
            confidence=0.99,
            source="mock",
            frame_id=frame_id,
            embedding_model="mock-sha256-v1",
        )

    def _insightface_embeddings(
        self,
        *,
        image_bytes: bytes,
        frame_id: str | None,
        width: int | None,
        height: int | None,
    ) -> list[FaceEmbedding]:
        try:
            import cv2  # type: ignore
            import numpy as np  # type: ignore
        except ImportError as exc:
            raise RuntimeError("InsightFace provider requires numpy and opencv-python.") from exc

        app = self._get_insightface_app()
        image_array = np.frombuffer(image_bytes, dtype=np.uint8)
        image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
        if image is None:
            return []

        image_height, image_width = image.shape[:2]
        width = width or image_width
        height = height or image_height

        faces = app.get(image)
        embeddings: list[FaceEmbedding] = []
        for face in faces:
            raw_embedding = getattr(face, "normed_embedding", None)
            if raw_embedding is None:
                raw_embedding = getattr(face, "embedding", None)
            if raw_embedding is None:
                continue
            vector = _normalize([float(value) for value in raw_embedding])
            bbox = self._normalize_bbox(getattr(face, "bbox", None), width=width, height=height)
            embeddings.append(
                FaceEmbedding(
                    embedding=vector,
                    bbox=bbox,
                    confidence=float(getattr(face, "det_score", 0.0) or 0.0),
                    source="insightface",
                    frame_id=frame_id,
                    embedding_model=settings.insightface_model_name,
                )
            )
        return embeddings

    def _get_insightface_app(self):
        if self._insightface_app is not None:
            return self._insightface_app
        try:
            from insightface.app import FaceAnalysis  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "FACE_RECOGNITION_PROVIDER=insightface requires insightface and onnxruntime. "
                "Install them or use FACE_RECOGNITION_PROVIDER=mock."
            ) from exc

        app = FaceAnalysis(name=settings.insightface_model_name)
        app.prepare(ctx_id=settings.insightface_ctx_id, det_size=settings.insightface_det_size)
        self._insightface_app = app
        return app

    @staticmethod
    def _normalize_bbox(raw_bbox, *, width: int, height: int) -> dict[str, Any] | None:
        if raw_bbox is None or width <= 0 or height <= 0:
            return None
        x1, y1, x2, y2 = [float(value) for value in raw_bbox[:4]]
        x = max(0.0, min(1.0, x1 / width))
        y = max(0.0, min(1.0, y1 / height))
        w = max(0.0, min(1.0, (x2 - x1) / width))
        h = max(0.0, min(1.0, (y2 - y1) / height))
        return {"x": x, "y": y, "w": w, "h": h, "unit": "normalized"}


face_embedding_runtime = FaceEmbeddingRuntime()
