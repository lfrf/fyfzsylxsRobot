from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Any

from config import settings
from models import FaceIdentityRequest, FaceIdentityResponse, FaceIdentityResult, FaceObservation
from services.face_database import FaceDatabase, FaceMatch
from services.face_embedding_runtime import FaceEmbedding, FaceEmbeddingRuntime, face_embedding_runtime


@dataclass(slots=True)
class _FramePayload:
    image_bytes: bytes
    frame_id: str | None = None
    width: int | None = None
    height: int | None = None


class FaceIdentityService:
    def __init__(
        self,
        *,
        database: FaceDatabase | None = None,
        runtime: FaceEmbeddingRuntime | None = None,
    ) -> None:
        self.database = database or FaceDatabase()
        self.runtime = runtime or face_embedding_runtime

    def extract_identity(self, request: FaceIdentityRequest) -> FaceIdentityResponse:
        frames = self._select_frames(request)
        observations: list[FaceObservation] = []
        candidates: list[tuple[FaceEmbedding, FaceMatch, FaceObservation]] = []

        for frame in frames:
            embeddings = self.runtime.extract(
                image_bytes=frame.image_bytes,
                frame_id=frame.frame_id,
                width=frame.width,
                height=frame.height,
            )
            for embedding in embeddings:
                match = self.database.match_or_create(
                    embedding=embedding.embedding,
                    threshold=settings.face_match_threshold,
                    create_unknown=settings.face_create_unknown,
                    source=embedding.source,
                    bbox=embedding.bbox,
                    embedding_model=embedding.embedding_model,
                )
                observation = self._build_observation(embedding=embedding, match=match)
                observations.append(observation)
                candidates.append((embedding, match, observation))

        if not candidates:
            return FaceIdentityResponse(
                face_identity=FaceIdentityResult(
                    face_detected=False,
                    source=self.runtime.provider,
                ),
                face_observations=[],
                processed_frame_count=len(frames),
                provider=self.runtime.provider,
            )

        primary_embedding, primary_match, primary_observation = self._choose_primary(candidates)
        primary_observation.is_primary = True
        primary_record = primary_match.record or {}
        is_known = bool(primary_match.record and not primary_match.created)
        return FaceIdentityResponse(
            face_identity=FaceIdentityResult(
                face_detected=True,
                face_id=primary_record.get("face_id"),
                user_id=primary_record.get("user_id"),
                is_known=is_known,
                match_confidence=primary_match.confidence,
                bbox=primary_embedding.bbox,
                source=primary_embedding.source,
                embedding_model=primary_embedding.embedding_model,
                seen_count=primary_record.get("seen_count"),
                last_seen_at=primary_record.get("last_seen_at"),
            ),
            face_observations=observations,
            processed_frame_count=len(frames),
            provider=self.runtime.provider,
        )

    def _select_frames(self, request: FaceIdentityRequest) -> list[_FramePayload]:
        if request.image_base64:
            return [
                _FramePayload(
                    image_bytes=self._decode_base64(request.image_base64),
                    frame_id=request.frame_id or "image",
                )
            ]

        frames: list[_FramePayload] = []
        for frame in request.video_frames:
            if not frame.image_base64:
                continue
            frames.append(
                _FramePayload(
                    image_bytes=self._decode_base64(frame.image_base64),
                    frame_id=frame.frame_id,
                    width=frame.width,
                    height=frame.height,
                )
            )
        return frames[:3]

    @staticmethod
    def _decode_base64(value: str) -> bytes:
        payload = value.split(",", 1)[1] if "," in value and value.startswith("data:") else value
        return base64.b64decode(payload)

    @staticmethod
    def _build_observation(*, embedding: FaceEmbedding, match: FaceMatch) -> FaceObservation:
        record: dict[str, Any] = match.record or {}
        return FaceObservation(
            face_id=record.get("face_id"),
            user_id=record.get("user_id"),
            is_primary=False,
            is_known=bool(record and not match.created),
            confidence=embedding.confidence,
            match_confidence=match.confidence,
            bbox=embedding.bbox,
            source=embedding.source,
            frame_id=embedding.frame_id,
            embedding_model=embedding.embedding_model,
            seen_count=record.get("seen_count"),
            last_seen_at=record.get("last_seen_at"),
        )

    @staticmethod
    def _choose_primary(
        candidates: list[tuple[FaceEmbedding, FaceMatch, FaceObservation]]
    ) -> tuple[FaceEmbedding, FaceMatch, FaceObservation]:
        def score(candidate: tuple[FaceEmbedding, FaceMatch, FaceObservation]) -> tuple[float, float, float]:
            embedding = candidate[0]
            bbox = embedding.bbox or {}
            w = float(bbox.get("w") or 0.0)
            h = float(bbox.get("h") or 0.0)
            x = float(bbox.get("x") or 0.0)
            y = float(bbox.get("y") or 0.0)
            area = w * h
            center_x = x + w / 2.0
            center_y = y + h / 2.0
            center_distance = ((center_x - 0.5) ** 2 + (center_y - 0.5) ** 2) ** 0.5
            center_score = max(0.0, 1.0 - center_distance)
            confidence = float(embedding.confidence or 0.0)
            return (center_score, area, confidence)

        return max(candidates, key=score)


face_identity_service = FaceIdentityService()
