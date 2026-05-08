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
        extracted_embeddings: list[FaceEmbedding] = []

        for frame in frames:
            embeddings = self.runtime.extract(
                image_bytes=frame.image_bytes,
                frame_id=frame.frame_id,
                width=frame.width,
                height=frame.height,
            )
            extracted_embeddings.extend(embeddings)

        if not extracted_embeddings:
            return FaceIdentityResponse(
                face_identity=FaceIdentityResult(
                    face_detected=False,
                    needs_username_registration=False,
                    source=self.runtime.provider,
                ),
                face_observations=[],
                processed_frame_count=len(frames),
                provider=self.runtime.provider,
            )

        primary_embedding = self._choose_primary_embedding(extracted_embeddings)
        primary_match = self._match_embeddings(extracted_embeddings)
        observations = [
            self._build_observation(embedding=embedding, match=primary_match) for embedding in extracted_embeddings
        ]
        primary_observation = min(
            observations,
            key=lambda observation: 0 if observation.frame_id == primary_embedding.frame_id else 1,
        )
        primary_observation.is_primary = True
        primary_record = primary_match.record or {}
        is_ready = primary_match.ready_for_registration
        is_known = bool(primary_record and not primary_match.created and is_ready)
        observation_count = primary_record.get("observation_count")
        match_count = primary_record.get("match_count")
        seen_count = primary_record.get("seen_count")
        if seen_count is None:
            seen_count = match_count
        needs_username_registration = bool(is_ready) and (
            not bool(primary_record.get("user_id")) or not bool(primary_record.get("display_name"))
        )
        return FaceIdentityResponse(
            face_identity=FaceIdentityResult(
                face_detected=True,
                face_id=primary_record.get("face_id") if is_ready else None,
                user_id=primary_record.get("user_id") if is_ready else None,
                is_known=is_known,
                needs_username_registration=needs_username_registration,
                match_confidence=primary_match.confidence,
                bbox=primary_embedding.bbox,
                source=primary_embedding.source,
                embedding_model=primary_embedding.embedding_model,
                observation_count=observation_count,
                match_count=match_count,
                seen_count=seen_count,
                last_seen_at=primary_record.get("last_seen_at"),
            ),
            face_observations=observations,
            processed_frame_count=len(frames),
            provider=self.runtime.provider,
        )

    def _match_embeddings(self, embeddings: list[FaceEmbedding]) -> FaceMatch:
        if embeddings and all(embedding.source == "mock" for embedding in embeddings):
            best_record, best_score = self.database.find_best_match(embeddings[0].embedding)
            return FaceMatch(record=best_record, confidence=best_score, created=False)

        return self.database.match_or_create_many(
            embeddings=[
                {
                    "embedding": embedding.embedding,
                    "source": embedding.source,
                    "bbox": embedding.bbox,
                    "embedding_model": embedding.embedding_model,
                }
                for embedding in embeddings
            ],
            threshold=settings.face_match_threshold,
            create_unknown=settings.face_create_unknown,
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
        observation_count = record.get("observation_count")
        match_count = record.get("match_count")
        seen_count = record.get("seen_count")
        if seen_count is None:
            seen_count = match_count
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
            observation_count=observation_count,
            match_count=match_count,
            seen_count=seen_count,
            last_seen_at=record.get("last_seen_at"),
        )

    @staticmethod
    def _choose_primary_embedding(embeddings: list[FaceEmbedding]) -> FaceEmbedding:
        def score(embedding: FaceEmbedding) -> tuple[float, float, float]:
            bbox = embedding.bbox or {}
            w = float(bbox.get("w") or 0.0)
            h = float(bbox.get("h") or 0.0)
            x = float(bbox.get("x") or 0.0)
            y = float(bbox.get("y") or 0.0)
            area = w * h
            confidence = float(embedding.confidence or 0.0)
            center_x = x + w / 2.0
            center_y = y + h / 2.0
            center_distance = ((center_x - 0.5) ** 2 + (center_y - 0.5) ** 2) ** 0.5
            center_score = max(0.0, 1.0 - center_distance)
            return (area, confidence, center_score)

        return max(embeddings, key=score)


face_identity_service = FaceIdentityService()
