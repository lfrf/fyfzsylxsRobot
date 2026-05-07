from __future__ import annotations

import json
import math
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import settings


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_embedding(embedding: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in embedding))
    if norm <= 0:
        return [0.0 for _ in embedding]
    return [float(value) / norm for value in embedding]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    left_norm = _normalize_embedding(left)
    right_norm = _normalize_embedding(right)
    return max(0.0, min(1.0, sum(a * b for a, b in zip(left_norm, right_norm))))


@dataclass(slots=True)
class FaceMatch:
    record: dict[str, Any] | None
    confidence: float | None
    created: bool = False


class FaceDatabase:
    def __init__(self, db_dir: str | Path | None = None) -> None:
        self.db_dir = Path(db_dir or settings.face_db_dir)
        self.db_path = self.db_dir / "faces.json"

    def list_faces(self) -> list[dict[str, Any]]:
        return list(self._load().get("faces", []))

    def get_face(self, face_id: str) -> dict[str, Any] | None:
        for record in self.list_faces():
            if record.get("face_id") == face_id:
                return record
        return None

    def find_best_match(self, embedding: list[float]) -> tuple[dict[str, Any] | None, float | None]:
        best_record: dict[str, Any] | None = None
        best_score: float | None = None
        for record in self.list_faces():
            score = cosine_similarity(embedding, record.get("embedding") or [])
            if best_score is None or score > best_score:
                best_record = record
                best_score = score
        return best_record, best_score

    def match_or_create(
        self,
        *,
        embedding: list[float],
        threshold: float | None = None,
        create_unknown: bool | None = None,
        source: str = "mock",
        bbox: dict[str, Any] | None = None,
        embedding_model: str | None = None,
    ) -> FaceMatch:
        threshold = settings.face_match_threshold if threshold is None else threshold
        create_unknown = settings.face_create_unknown if create_unknown is None else create_unknown
        source = (source or "").strip().lower()
        if not self._is_persistable_face(source=source, embedding=embedding, embedding_model=embedding_model):
            return FaceMatch(record=None, confidence=None, created=False)

        normalized = _normalize_embedding(embedding)

        data = self._load()
        best_record: dict[str, Any] | None = None
        best_score: float | None = None
        for record in data.get("faces", []):
            record_source = str(record.get("source") or "").strip().lower()
            if record_source != source:
                continue
            score = cosine_similarity(normalized, record.get("embedding") or [])
            if best_score is None or score > best_score:
                best_record = record
                best_score = score

        if best_record is not None and best_score is not None and best_score >= threshold:
            new_count = int(best_record.get("visual_seen_count") or best_record.get("seen_count") or 0) + 1
            best_record["seen_count"] = new_count
            best_record["visual_seen_count"] = new_count
            best_record["last_seen_at"] = _now_iso()
            if bbox:
                best_record["last_bbox"] = bbox
            self._save(data)
            return FaceMatch(record=best_record, confidence=best_score, created=False)

        if not create_unknown:
            return FaceMatch(record=None, confidence=best_score, created=False)

        record = {
            "face_id": f"face_{uuid.uuid4().hex[:12]}",
            "user_id": None,
            "embedding": normalized,
            "seen_count": 1,
            "visual_seen_count": 1,
            "created_at": _now_iso(),
            "last_seen_at": _now_iso(),
            "source": source,
            "embedding_model": embedding_model,
            "last_bbox": bbox,
        }
        data.setdefault("faces", []).append(record)
        self._save(data)
        return FaceMatch(record=record, confidence=best_score, created=True)

    def _is_persistable_face(
        self,
        *,
        source: str,
        embedding: list[float],
        embedding_model: str | None,
    ) -> bool:
        if source == "mock" and not settings.face_store_mock_records:
            return False
        if source != "insightface":
            return bool(source == "mock" and settings.face_store_mock_records)
        if not embedding:
            return False
        if not (embedding_model or "").strip():
            return False
        return True

    def _load(self) -> dict[str, Any]:
        if not self.db_path.exists():
            return {"faces": []}
        try:
            with self.db_path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (json.JSONDecodeError, OSError):
            return {"faces": []}
        if not isinstance(data, dict):
            return {"faces": []}
        faces = data.get("faces")
        if not isinstance(faces, list):
            data["faces"] = []
        return data

    def _save(self, data: dict[str, Any]) -> None:
        self.db_dir.mkdir(parents=True, exist_ok=True)
        tmp_path = self.db_path.with_suffix(".tmp")
        with tmp_path.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
        tmp_path.replace(self.db_path)
