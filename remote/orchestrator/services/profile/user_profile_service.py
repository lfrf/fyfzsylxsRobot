from __future__ import annotations

from typing import Any

from config import settings
from logging_utils import log_event

from .memory_store import MemoryStore, memory_store
from .profile_builder import ProfileBuilder, profile_builder
from .profile_prompt import ProfilePromptBuilder
from .profile_store import ProfileStore, profile_store
from .schemas import IdentityResolution, MemoryEvent, MemoryWriteResult, ProfileContextResult, SummaryUpdateResult, safe_identifier


class UserProfileService:
    """Resolve active robot user identity and coordinate profile state."""

    def __init__(
        self,
        *,
        store: ProfileStore | None = None,
        memories: MemoryStore | None = None,
        builder: ProfileBuilder | None = None,
        prompt_builder: ProfilePromptBuilder | None = None,
    ) -> None:
        self.store = store or profile_store
        self.memories = memories or memory_store
        self.builder = builder or profile_builder
        self.prompt_builder = prompt_builder or ProfilePromptBuilder(
            store=self.store,
            memories=self.memories,
            builder=self.builder,
        )

    def resolve_identity(self, request: Any) -> IdentityResolution:
        options = request.request_options if isinstance(getattr(request, "request_options", None), dict) else {}
        mock_user_id = self._clean(options.get("mock_user_id"))
        mock_display_name = self._clean(options.get("mock_display_name"))
        option_face_id = self._clean(options.get("face_id"))
        vision_face_id = self._face_id_from_vision(getattr(request, "vision_context", None))

        if mock_user_id:
            profile = self.store.ensure_user(mock_user_id, display_name=mock_display_name)
            identity = IdentityResolution(
                user_id=profile.user_id,
                identity_source="mock_user_id",
                face_id=None,
                display_name=profile.display_name,
                is_anonymous=False,
                profile=profile,
            )
            self._log_identity(identity)
            return identity

        face_id = option_face_id or vision_face_id
        if face_id:
            existing_user_id = self.store.get_user_id_for_face(face_id)
            if existing_user_id:
                profile = self.store.ensure_user(existing_user_id, face_id=face_id)
            else:
                profile = self.store.create_user_for_face(face_id)
            identity = IdentityResolution(
                user_id=profile.user_id,
                identity_source="face_id" if option_face_id else "vision_face_identity",
                face_id=safe_identifier(face_id, fallback="face"),
                display_name=profile.display_name,
                is_anonymous=False,
                profile=profile,
            )
            self._log_identity(identity)
            return identity

        session_id = safe_identifier(getattr(request, "session_id", None), fallback="session")
        anonymous_user_id = f"anonymous_{session_id}"
        profile = self.store.ensure_user(anonymous_user_id, display_name=mock_display_name or "匿名用户")
        identity = IdentityResolution(
            user_id=profile.user_id,
            identity_source="anonymous_session",
            face_id=None,
            display_name=profile.display_name,
            is_anonymous=True,
            profile=profile,
        )
        self._log_identity(identity)
        return identity

    def build_profile_context(self, *, user_id: str, mode_id: str | None = None) -> ProfileContextResult:
        result = self.prompt_builder.build_for_user(user_id=user_id, mode_id=mode_id)
        log_event(
            "profile_context_built",
            user_id=user_id,
            mode_id=mode_id,
            profile_context_chars=result.chars,
            used=bool(result.context),
        )
        return result

    def record_turn(
        self,
        *,
        user_id: str,
        session_id: str,
        turn_id: str,
        mode_id: str,
        asr_text: str,
        reply_text: str,
        emotion_label: str | None = None,
        face_id: str | None = None,
        request_options: dict | None = None,
    ) -> MemoryWriteResult:
        if not settings.profile_memory_enabled:
            return MemoryWriteResult(written=False, summary_updated=False)
        try:
            event = MemoryEvent(
                user_id=user_id,
                session_id=session_id,
                turn_id=str(turn_id),
                mode=mode_id,
                asr_text=asr_text or "",
                reply_text=reply_text or "",
                emotion=emotion_label,
                face_id=face_id,
                tags=self._event_tags(asr_text, mode_id),
            )
            self.memories.append_event(event)
            unsummarized_count = self.memories.count_unsummarized(user_id)
            summary_updated = False
            options = request_options if isinstance(request_options, dict) else {}
            if options.get("force_profile_summarize") or unsummarized_count >= settings.profile_summarize_every_turns:
                summary = self.summarize_user(user_id)
                summary_updated = summary.updated
                unsummarized_count = self.memories.count_unsummarized(user_id)
            log_event(
                "profile_memory_event_written",
                user_id=user_id,
                memory_id=event.memory_id,
                summary_updated=summary_updated,
                unsummarized_count=unsummarized_count,
            )
            return MemoryWriteResult(
                written=True,
                memory_id=event.memory_id,
                summary_updated=summary_updated,
                unsummarized_count=unsummarized_count,
            )
        except Exception as exc:
            log_event(
                "profile_memory_event_error",
                user_id=user_id,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            return MemoryWriteResult(written=False, summary_updated=False, error=str(exc))

    def summarize_user(self, user_id: str) -> SummaryUpdateResult:
        profile = self.store.get_profile(user_id)
        if profile is None:
            return SummaryUpdateResult(updated=False, summarized_count=0, error="profile_not_found")
        events = self.memories.unsummarized_events(user_id)
        result = self.builder.summarize(profile, events)
        if result.updated:
            self.store.save_profile(profile)
            self.memories.mark_summarized(user_id, {event.memory_id for event in events})
            log_event(
                "profile_summary_updated",
                user_id=user_id,
                summarized_count=result.summarized_count,
            )
        return result

    def _face_id_from_vision(self, vision_context: Any) -> str | None:
        if vision_context is None:
            return None
        face_identity = getattr(vision_context, "face_identity", None)
        if isinstance(face_identity, dict):
            return self._clean(face_identity.get("face_id"))
        return self._clean(getattr(face_identity, "face_id", None))

    def _clean(self, value: Any) -> str | None:
        text = str(value or "").strip()
        return text or None

    def _log_identity(self, identity: IdentityResolution) -> None:
        log_event(
            "profile_identity_resolved",
            user_id=identity.user_id,
            identity_source=identity.identity_source,
            face_id=identity.face_id,
            display_name=identity.display_name,
            is_anonymous=identity.is_anonymous,
        )

    def _event_tags(self, text: str, mode_id: str) -> list[str]:
        tags = [f"mode:{mode_id}"]
        if any(token in text for token in ("累", "困", "疲惫")):
            tags.append("emotion:tired")
        if any(token in text for token in ("学习", "复习", "课程")):
            tags.append("topic:learning")
        if mode_id == "game" or any(token in text for token in ("游戏", "猜谜", "接龙")):
            tags.append("topic:game")
        return tags


user_profile_service = UserProfileService()
