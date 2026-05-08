from __future__ import annotations

import json
import logging
import math
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Any

from config import settings

logger = logging.getLogger(__name__)


def _configure_face_diagnostic_logger() -> None:
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if any(getattr(handler, "_robotmatch_face_diagnostics", False) for handler in logger.handlers):
        return
    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    handler._robotmatch_face_diagnostics = True  # type: ignore[attr-defined]
    logger.addHandler(handler)


_configure_face_diagnostic_logger()


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
    identity_status: str | None = None
    ready_for_registration: bool = True
    decision_reason: str | None = None


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
        return self.match_or_create_many(
            embeddings=[
                {
                    "embedding": embedding,
                    "source": source,
                    "bbox": bbox,
                    "embedding_model": embedding_model,
                }
            ],
            threshold=threshold,
            create_unknown=create_unknown,
        )

    def match_or_create_many(
        self,
        *,
        embeddings: list[dict[str, Any]],
        threshold: float | None = None,
        create_unknown: bool | None = None,
    ) -> FaceMatch:
        threshold = settings.face_match_threshold if threshold is None else threshold
        create_unknown = settings.face_create_unknown if create_unknown is None else create_unknown
        normalized_items = [
            {
                **item,
                "embedding": _normalize_embedding(item.get("embedding") or []),
            }
            for item in embeddings
            if item.get("embedding")
        ]
        if not normalized_items:
            return FaceMatch(record=None, confidence=None, created=False, ready_for_registration=False)

        data = self._load()
        faces = data.get("faces", [])
        scored_records = self._rank_records_many([item["embedding"] for item in normalized_items], faces)
        chosen_record, chosen_score, decision_reason = self._choose_record_from_scores(scored_records, threshold)
        best_record = scored_records[0]["record"] if scored_records else None
        best_score = scored_records[0]["score"] if scored_records else None
        top_candidates = [
            {
                "face_id": item["record"].get("face_id"),
                "user_id": item["record"].get("user_id"),
                "score": round(item["score"], 6),
                "max_score": round(item["max_score"], 6),
                "support_count": item["support_count"],
                "embedding_count": len(self._record_embeddings(item["record"])),
            }
            for item in scored_records[: settings.face_match_log_top_k]
        ]

        if chosen_record is not None and chosen_score is not None and chosen_score >= threshold:
            self._update_matched_record(chosen_record, normalized_items, chosen_score)
            self._maybe_merge_close_unknown(
                data=data,
                chosen_record=chosen_record,
                scored_records=scored_records,
                threshold=threshold,
            )
            self._save(data)
            identity_status = self._record_identity_status(chosen_record)
            self._log_match_result(
                created=False,
                threshold=threshold,
                best_record=chosen_record,
                best_score=chosen_score,
                top_candidates=top_candidates,
                decision_reason=decision_reason,
                ready_for_registration=self._ready_for_registration(chosen_record),
            )
            return FaceMatch(
                record=chosen_record,
                confidence=chosen_score,
                created=False,
                identity_status=identity_status,
                ready_for_registration=self._ready_for_registration(chosen_record),
                decision_reason=decision_reason,
            )

        if not create_unknown:
            self._log_match_result(
                created=False,
                threshold=threshold,
                best_record=best_record,
                best_score=best_score,
                top_candidates=top_candidates,
                create_unknown=False,
                decision_reason="no_match_create_disabled",
                ready_for_registration=False,
            )
            return FaceMatch(
                record=None,
                confidence=best_score,
                created=False,
                ready_for_registration=False,
                decision_reason="no_match_create_disabled",
            )

        primary_item = self._choose_primary_embedding_item(normalized_items)
        record = {
            "face_id": f"face_{uuid.uuid4().hex[:12]}",
            "user_id": None,
            "embedding": primary_item["embedding"],
            "embeddings": [],
            "aliases": [],
            "identity_status": "pending",
            "pending_observation_count": 1,
            "observation_count": len(normalized_items),
            "match_count": 0,
            "seen_count": 0,
            "created_at": _now_iso(),
            "last_seen_at": _now_iso(),
            "source": primary_item.get("source"),
            "embedding_model": primary_item.get("embedding_model"),
            "last_bbox": primary_item.get("bbox"),
        }
        for item in normalized_items:
            self._append_embedding(
                record,
                item["embedding"],
                source=item.get("source"),
                bbox=item.get("bbox"),
                embedding_model=item.get("embedding_model"),
                best_score=None,
                force=True,
            )
        data.setdefault("faces", []).append(record)
        self._save(data)
        self._log_match_result(
            created=True,
            threshold=threshold,
            best_record=best_record,
            best_score=best_score,
            created_record=record,
            top_candidates=top_candidates,
            decision_reason="created_pending_unknown",
            ready_for_registration=self._ready_for_registration(record),
        )
        return FaceMatch(
            record=record,
            confidence=best_score,
            created=True,
            identity_status=self._record_identity_status(record),
            ready_for_registration=self._ready_for_registration(record),
            decision_reason="created_pending_unknown",
        )

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

    def _rank_records_many(self, embeddings: list[list[float]], records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        ranked: list[dict[str, Any]] = []
        for record in records:
            scores = [self._score_record(embedding, record) for embedding in embeddings]
            if not scores:
                continue
            max_score = max(scores)
            near_threshold = max(settings.face_registered_priority_min_score, settings.face_match_threshold - 0.05)
            support_count = sum(1 for score in scores if score >= near_threshold)
            top_scores = sorted(scores, reverse=True)[:3]
            mean_top_score = sum(top_scores) / len(top_scores)
            support_ratio = support_count / max(1, len(scores))
            identity_bonus = self._identity_confidence_bonus(record)
            aggregate_score = (0.62 * max_score) + (0.28 * mean_top_score) + (0.07 * support_ratio) + identity_bonus
            ranked.append(
                {
                    "record": record,
                    "score": min(1.0, aggregate_score),
                    "max_score": max_score,
                    "mean_top_score": mean_top_score,
                    "support_count": support_count,
                    "support_ratio": support_ratio,
                    "identity_bonus": identity_bonus,
                }
            )
        ranked.sort(key=lambda item: item["score"], reverse=True)
        return ranked

    def _choose_record_from_scores(
        self, scored_records: list[dict[str, Any]], threshold: float
    ) -> tuple[dict[str, Any] | None, float | None, str]:
        if not scored_records:
            return None, None, "no_candidates"

        top = scored_records[0]
        chosen = top
        reason = "top_aggregate_score"
        registered_candidates = [
            item
            for item in scored_records
            if item["record"].get("user_id")
            and item["max_score"] >= settings.face_registered_priority_min_score
            and item["support_count"] > 0
        ]
        if registered_candidates:
            registered = registered_candidates[0]
            dynamic_margin = self._registered_priority_margin(registered["record"], registered["support_count"])
            close_enough = top["score"] - registered["score"] <= dynamic_margin
            strong_enough = registered["score"] >= min(threshold, settings.face_registered_priority_min_score)
            if registered is not top and close_enough and strong_enough:
                chosen = registered
                reason = "registered_identity_close_evidence"

        return chosen["record"], chosen["score"], reason

    def _registered_priority_margin(self, record: dict[str, Any], support_count: int) -> float:
        embedding_count = min(4, len(self._record_embeddings(record)))
        history_bonus = 0.004 * embedding_count
        support_bonus = 0.006 * min(3, support_count)
        return min(0.08, settings.face_registered_priority_margin + history_bonus + support_bonus)

    def _identity_confidence_bonus(self, record: dict[str, Any]) -> float:
        if not record.get("user_id"):
            return 0.0
        embedding_count = min(5, len(self._record_embeddings(record)))
        seen_count = min(10, int(record.get("seen_count") or record.get("match_count") or 0))
        return min(0.045, 0.015 + 0.004 * embedding_count + 0.001 * seen_count)

    def _update_matched_record(
        self,
        record: dict[str, Any],
        embedding_items: list[dict[str, Any]],
        best_score: float | None,
    ) -> None:
        observation_count = int(record.get("observation_count") or record.get("seen_count") or 0) + len(embedding_items)
        match_count = int(record.get("match_count") or record.get("seen_count") or 0) + 1
        record["observation_count"] = observation_count
        record["match_count"] = match_count
        record["seen_count"] = match_count
        record["last_seen_at"] = _now_iso()

        if self._record_identity_status(record) == "pending":
            pending_count = int(record.get("pending_observation_count") or 0) + 1
            record["pending_observation_count"] = pending_count
            if pending_count >= settings.face_unknown_confirm_observations:
                record["identity_status"] = "stable"

        primary_item = self._choose_primary_embedding_item(embedding_items)
        record["source"] = primary_item.get("source") or record.get("source")
        if primary_item.get("bbox"):
            record["last_bbox"] = primary_item.get("bbox")
        if primary_item.get("embedding_model"):
            record["embedding_model"] = primary_item.get("embedding_model")

        for item in embedding_items:
            self._append_embedding(
                record,
                item["embedding"],
                source=item.get("source"),
                bbox=item.get("bbox"),
                embedding_model=item.get("embedding_model"),
                best_score=best_score,
            )

    def _maybe_merge_close_unknown(
        self,
        *,
        data: dict[str, Any],
        chosen_record: dict[str, Any],
        scored_records: list[dict[str, Any]],
        threshold: float,
    ) -> None:
        if not settings.face_auto_merge_enabled or not chosen_record.get("user_id"):
            return
        chosen_score = next(
            (item["score"] for item in scored_records if item["record"] is chosen_record),
            None,
        )
        if chosen_score is None:
            return
        for item in scored_records:
            duplicate = item["record"]
            if duplicate is chosen_record or duplicate.get("user_id"):
                continue
            if item["max_score"] < max(settings.face_registered_priority_min_score, threshold - 0.05):
                continue
            if abs(chosen_score - item["score"]) > settings.face_auto_merge_margin:
                continue
            self._merge_records_in_data(data, primary=chosen_record, duplicate=duplicate)
            logger.info(
                "face_auto_merge_close_unknown primary_face_id=%s duplicate_face_id=%s primary_score=%s duplicate_score=%s",
                chosen_record.get("face_id"),
                duplicate.get("face_id"),
                round(chosen_score, 6),
                round(item["score"], 6),
            )
            return

    def _merge_records_in_data(
        self,
        data: dict[str, Any],
        *,
        primary: dict[str, Any],
        duplicate: dict[str, Any],
    ) -> None:
        aliases = set(primary.get("aliases") or [])
        aliases.add(str(duplicate.get("face_id")))
        aliases.update(str(alias) for alias in (duplicate.get("aliases") or []))
        primary["aliases"] = sorted(alias for alias in aliases if alias and alias != primary.get("face_id"))
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
        data["faces"] = [record for record in data.get("faces", []) if record is not duplicate]

    def _choose_primary_embedding_item(self, embedding_items: list[dict[str, Any]]) -> dict[str, Any]:
        def score(item: dict[str, Any]) -> tuple[float, float]:
            bbox = item.get("bbox") or {}
            area = float(bbox.get("w") or 0.0) * float(bbox.get("h") or 0.0)
            return (area, 1.0 if item.get("embedding") else 0.0)

        return max(embedding_items, key=score)

    def _record_identity_status(self, record: dict[str, Any]) -> str:
        if record.get("user_id"):
            return "registered"
        return str(record.get("identity_status") or "stable")

    def _ready_for_registration(self, record: dict[str, Any]) -> bool:
        if record.get("user_id"):
            return True
        return self._record_identity_status(record) != "pending"

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
        decision_reason: str | None = None,
        ready_for_registration: bool | None = None,
    ) -> None:
        logger.info(
            "face_match_result created=%s create_unknown=%s threshold=%.4f best_face_id=%s best_user_id=%s "
            "best_score=%s created_face_id=%s created_user_id=%s decision_reason=%s ready_for_registration=%s "
            "top_candidates=%s",
            created,
            create_unknown,
            threshold,
            None if best_record is None else best_record.get("face_id"),
            None if best_record is None else best_record.get("user_id"),
            None if best_score is None else round(best_score, 6),
            None if created_record is None else created_record.get("face_id"),
            None if created_record is None else created_record.get("user_id"),
            decision_reason,
            ready_for_registration,
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
