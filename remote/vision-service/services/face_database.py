from __future__ import annotations

import json
import logging
import math
import uuid
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Any

from config import settings

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    try:
        return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()
    except Exception:
        return datetime.now().astimezone().isoformat()


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
            if record.get("face_id") == face_id or face_id in (record.get("aliases") or []):
                return record
        return None

    def link_user(self, *, face_id: str, user_id: str, display_name: str | None = None) -> dict[str, Any] | None:
        data = self._load()
        for record in data.get("faces", []):
            if record.get("face_id") != face_id and face_id not in (record.get("aliases") or []):
                continue
            record["user_id"] = user_id
            if display_name is not None:
                record["display_name"] = display_name
            record["last_seen_at"] = _now_iso()
            self._save(data)
            return record
        record = {
            "face_id": face_id,
            "user_id": user_id,
            "display_name": display_name,
            "embedding": [],
            "observation_count": 0,
            "match_count": 0,
            "seen_count": 0,
            "created_at": _now_iso(),
            "last_seen_at": _now_iso(),
            "source": "orchestrator_link_user",
            "embedding_model": None,
            "last_bbox": None,
        }
        data.setdefault("faces", []).append(record)
        self._save(data)
        return record

    def find_best_match(self, embedding: list[float]) -> tuple[dict[str, Any] | None, float | None]:
        best_record: dict[str, Any] | None = None
        best_score: float | None = None
        for record in self.list_faces():
            score = self._score_record(embedding, record)
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
        normalized = _normalize_embedding(embedding)

        data = self._load()
        scored_records = self._rank_records(normalized, data.get("faces", []))
        best_record = scored_records[0][0] if scored_records else None
        best_score = scored_records[0][1] if scored_records else None
        top_candidates = [
            {
                "face_id": record.get("face_id"),
                "user_id": record.get("user_id"),
                "score": round(score, 6),
                "embedding_count": len(self._record_embeddings(record)),
            }
            for record, score in scored_records[: settings.face_match_log_top_k]
        ]

        if best_record is not None and best_score is not None and best_score >= threshold:
            observation_count = int(best_record.get("observation_count") or best_record.get("seen_count") or 0) + 1
            match_count = int(best_record.get("match_count") or best_record.get("seen_count") or 0) + 1
            best_record["observation_count"] = observation_count
            best_record["match_count"] = match_count
            best_record["seen_count"] = match_count
            best_record["last_seen_at"] = _now_iso()
            best_record["source"] = source or best_record.get("source")
            if bbox:
                best_record["last_bbox"] = bbox
            self._append_embedding(
                best_record,
                normalized,
                source=source,
                bbox=bbox,
                embedding_model=embedding_model,
                best_score=best_score,
            )
            self._save(data)
            self._log_match_result(
                created=False,
                threshold=threshold,
                best_record=best_record,
                best_score=best_score,
                top_candidates=top_candidates,
            )
            return FaceMatch(record=best_record, confidence=best_score, created=False)

        if not create_unknown:
            self._log_match_result(
                created=False,
                threshold=threshold,
                best_record=best_record,
                best_score=best_score,
                top_candidates=top_candidates,
                create_unknown=False,
            )
            return FaceMatch(record=None, confidence=best_score, created=False)

        record = {
            "face_id": f"face_{uuid.uuid4().hex[:12]}",
            "user_id": None,
            "embedding": normalized,
            "embeddings": [
                {
                    "embedding": normalized,
                    "created_at": _now_iso(),
                    "source": source,
                    "embedding_model": embedding_model,
                    "bbox": bbox,
                }
            ],
            "aliases": [],
            "observation_count": 1,
            "match_count": 0,
            "seen_count": 0,
            "created_at": _now_iso(),
            "last_seen_at": _now_iso(),
            "source": source,
            "embedding_model": embedding_model,
            "last_bbox": bbox,
        }
        data.setdefault("faces", []).append(record)
        self._save(data)
        self._log_match_result(
            created=True,
            threshold=threshold,
            best_record=best_record,
            best_score=best_score,
            created_record=record,
            top_candidates=top_candidates,
        )
        return FaceMatch(record=record, confidence=best_score, created=True)

    def merge_faces(self, *, primary_face_id: str, duplicate_face_id: str) -> dict[str, Any] | None:
        data = self._load()
        faces = data.get("faces", [])
        primary = self._find_record(faces, primary_face_id)
        duplicate = self._find_record(faces, duplicate_face_id)
        if primary is None or duplicate is None or primary is duplicate:
            return None

        aliases = set(primary.get("aliases") or [])
        aliases.add(str(duplicate.get("face_id")))
        aliases.update(str(alias) for alias in (duplicate.get("aliases") or []))
        primary["aliases"] = sorted(alias for alias in aliases if alias and alias != primary.get("face_id"))

        if not primary.get("user_id") and duplicate.get("user_id"):
            primary["user_id"] = duplicate.get("user_id")
        if not primary.get("display_name") and duplicate.get("display_name"):
            primary["display_name"] = duplicate.get("display_name")
        if duplicate.get("last_bbox"):
            primary["last_bbox"] = duplicate.get("last_bbox")

        for embedding in self._record_embeddings(duplicate):
            self._append_embedding(
                primary,
                embedding,
                source=duplicate.get("source"),
                bbox=duplicate.get("last_bbox"),
                embedding_model=duplicate.get("embedding_model"),
                best_score=None,
                force=True,
            )

        primary["observation_count"] = int(primary.get("observation_count") or 0) + int(
            duplicate.get("observation_count") or 0
        )
        primary["match_count"] = int(primary.get("match_count") or 0) + int(duplicate.get("match_count") or 0)
        primary["seen_count"] = int(primary.get("seen_count") or 0) + int(duplicate.get("seen_count") or 0)
        primary["last_seen_at"] = _now_iso()

        data["faces"] = [record for record in faces if record is not duplicate]
        self._save(data)
        logger.info(
            "face_records_merged primary_face_id=%s duplicate_face_id=%s aliases=%s embedding_count=%s",
            primary.get("face_id"),
            duplicate.get("face_id"),
            primary.get("aliases"),
            len(self._record_embeddings(primary)),
        )
        return primary

    def _rank_records(self, embedding: list[float], records: list[dict[str, Any]]) -> list[tuple[dict[str, Any], float]]:
        scored = [(record, self._score_record(embedding, record)) for record in records]
        scored.sort(key=lambda item: item[1], reverse=True)
        return scored

    def _score_record(self, embedding: list[float], record: dict[str, Any]) -> float:
        embeddings = self._record_embeddings(record)
        if not embeddings:
            return 0.0
        return max(cosine_similarity(embedding, existing) for existing in embeddings)

    def _record_embeddings(self, record: dict[str, Any]) -> list[list[float]]:
        embeddings: list[list[float]] = []
        primary = record.get("embedding")
        if isinstance(primary, list) and primary:
            embeddings.append(_normalize_embedding([float(value) for value in primary]))
        for item in record.get("embeddings") or []:
            raw = item.get("embedding") if isinstance(item, dict) else item
            if isinstance(raw, list) and raw:
                embeddings.append(_normalize_embedding([float(value) for value in raw]))

        unique: list[list[float]] = []
        seen: set[tuple[float, ...]] = set()
        for embedding in embeddings:
            key = tuple(round(value, 6) for value in embedding)
            if key in seen:
                continue
            seen.add(key)
            unique.append(embedding)
        return unique

    def _append_embedding(
        self,
        record: dict[str, Any],
        embedding: list[float],
        *,
        source: str | None,
        bbox: dict[str, Any] | None,
        embedding_model: str | None,
        best_score: float | None,
        force: bool = False,
    ) -> None:
        normalized = _normalize_embedding(embedding)
        existing = self._record_embeddings(record)
        if existing and not force:
            nearest = max(cosine_similarity(normalized, item) for item in existing)
            if nearest >= 1.0 - settings.face_embedding_append_min_delta:
                return

        history = record.get("embeddings")
        if not isinstance(history, list):
            history = []
        history.append(
            {
                "embedding": normalized,
                "created_at": _now_iso(),
                "source": source,
                "embedding_model": embedding_model,
                "bbox": bbox,
                "match_score": best_score,
            }
        )
        max_size = settings.face_embedding_history_size
        if len(history) > max_size:
            history = history[-max_size:]
        record["embeddings"] = history
        if not record.get("embedding"):
            record["embedding"] = normalized

    @staticmethod
    def _find_record(records: list[dict[str, Any]], face_id: str) -> dict[str, Any] | None:
        for record in records:
            if record.get("face_id") == face_id or face_id in (record.get("aliases") or []):
                return record
        return None

    def _log_match_result(
        self,
        *,
        created: bool,
        threshold: float,
        best_record: dict[str, Any] | None,
        best_score: float | None,
        top_candidates: list[dict[str, Any]],
        created_record: dict[str, Any] | None = None,
        create_unknown: bool = True,
    ) -> None:
        logger.info(
            "face_match_result created=%s create_unknown=%s threshold=%.4f best_face_id=%s best_user_id=%s "
            "best_score=%s created_face_id=%s created_user_id=%s top_candidates=%s",
            created,
            create_unknown,
            threshold,
            None if best_record is None else best_record.get("face_id"),
            None if best_record is None else best_record.get("user_id"),
            None if best_score is None else round(best_score, 6),
            None if created_record is None else created_record.get("face_id"),
            None if created_record is None else created_record.get("user_id"),
            json.dumps(top_candidates, ensure_ascii=False),
        )

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
