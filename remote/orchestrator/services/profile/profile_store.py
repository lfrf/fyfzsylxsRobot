from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from config import settings

from .schemas import UserProfile, safe_identifier, utc_now_iso


def _model_dump(model) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


class ProfileStore:
    """File-based user profile store for remote orchestrator."""

    def __init__(self, data_dir: str | Path | None = None) -> None:
        self.root = Path(data_dir or settings.profile_data_dir)
        self.memories_dir = self.root / "memories"
        self.snapshots_dir = self.root / "snapshots"
        self.users_path = self.root / "users.json"
        self.face_user_map_path = self.root / "face_user_map.json"

    def ensure_dirs(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.memories_dir.mkdir(parents=True, exist_ok=True)
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)

    def get_profile(self, user_id: str) -> UserProfile | None:
        user_id = safe_identifier(user_id, fallback="anonymous")
        path = self.snapshot_json_path(user_id)
        if not path.exists():
            return None
        data = self._read_json(path, default={})
        if not data:
            return None
        return UserProfile(**data)

    def ensure_user(
        self,
        user_id: str,
        *,
        display_name: str | None = None,
        face_id: str | None = None,
    ) -> UserProfile:
        self.ensure_dirs()
        safe_user_id = safe_identifier(user_id, fallback="anonymous")
        profile = self.get_profile(safe_user_id)
        now = utc_now_iso()
        if profile is None:
            profile = UserProfile(
                user_id=safe_user_id,
                display_name=display_name or "",
                created_at=now,
            )
        elif display_name:
            profile.display_name = display_name
        elif profile.display_name == "未命名用户":
            profile.display_name = ""

        profile.last_seen_at = now
        profile.seen_count += 1
        if face_id:
            safe_face_id = safe_identifier(face_id, fallback="face")
            if safe_face_id not in profile.face_ids:
                profile.face_ids.append(safe_face_id)
            self.map_face_to_user(safe_face_id, safe_user_id)
        self.save_profile(profile)
        return profile

    def create_user_for_face(self, face_id: str, *, display_name: str | None = None) -> UserProfile:
        safe_face_id = safe_identifier(face_id, fallback="face")
        existing_user_id = self.get_user_id_for_face(safe_face_id)
        if existing_user_id:
            return self.ensure_user(existing_user_id, display_name=display_name, face_id=safe_face_id)
        user_id = f"user_{safe_face_id}"
        profile = self.ensure_user(user_id, display_name=display_name, face_id=safe_face_id)
        self.map_face_to_user(safe_face_id, profile.user_id)
        return profile

    def save_profile(self, profile: UserProfile) -> None:
        self.ensure_dirs()
        self._write_json_atomic(self.snapshot_json_path(profile.user_id), _model_dump(profile))
        self.snapshot_md_path(profile.user_id).write_text(self._render_profile_markdown(profile), encoding="utf-8")
        users = self._load_users_index()
        users.setdefault("users", {})[profile.user_id] = {
            "user_id": profile.user_id,
            "display_name": profile.display_name,
            "last_seen_at": profile.last_seen_at,
            "snapshot": str(self.snapshot_json_path(profile.user_id)),
        }
        self._write_json_atomic(self.users_path, users)

    def get_user_id_for_face(self, face_id: str) -> str | None:
        face_map = self._load_face_map()
        return face_map.get(safe_identifier(face_id, fallback="face"))

    def get_profile_by_face(self, face_id: str) -> UserProfile | None:
        user_id = self.get_user_id_for_face(face_id)
        if not user_id:
            return None
        return self.get_profile(user_id)

    def map_face_to_user(self, face_id: str, user_id: str) -> None:
        self.ensure_dirs()
        face_map = self._load_face_map()
        face_map[safe_identifier(face_id, fallback="face")] = safe_identifier(user_id, fallback="anonymous")
        self._write_json_atomic(self.face_user_map_path, face_map)

    def snapshot_json_path(self, user_id: str) -> Path:
        return self.snapshots_dir / f"{safe_identifier(user_id, fallback='anonymous')}.json"

    def snapshot_md_path(self, user_id: str) -> Path:
        return self.snapshots_dir / f"{safe_identifier(user_id, fallback='anonymous')}.md"

    def storage_paths(self) -> dict[str, str]:
        return {
            "root": str(self.root),
            "users": str(self.users_path),
            "face_user_map": str(self.face_user_map_path),
            "memories": str(self.memories_dir),
            "snapshots": str(self.snapshots_dir),
        }

    def _load_users_index(self) -> dict[str, Any]:
        return self._read_json(self.users_path, default={"users": {}})

    def _load_face_map(self) -> dict[str, str]:
        return self._read_json(self.face_user_map_path, default={})

    def _read_json(self, path: Path, *, default):
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default

    def _write_json_atomic(self, path: Path, payload: Any) -> None:
        self.ensure_dirs()
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        tmp_path.replace(path)

    def _render_profile_markdown(self, profile: UserProfile) -> str:
        facts = ", ".join(f"{item.key}:{item.value}" for item in profile.facts[:8])
        title = profile.display_name or profile.user_id
        return "\n".join([
            f"# {title}",
            "",
            f"- user_id: {profile.user_id}",
            f"- face_ids: {', '.join(profile.face_ids)}",
            f"- preferred_mode: {profile.preferred_mode or ''}",
            f"- seen_count: {profile.seen_count}",
            "",
            "## Summary",
            profile.profile_summary or "",
            "",
            "## Recent Topics",
            ", ".join(profile.recent_topics[:8]),
            "",
            "## Learning Goals",
            ", ".join(profile.learning_goals[:8]),
            "",
            "## Emotional Notes",
            ", ".join(profile.emotional_notes[:8]),
            "",
            "## Facts",
            facts,
            "",
        ])


profile_store = ProfileStore()
