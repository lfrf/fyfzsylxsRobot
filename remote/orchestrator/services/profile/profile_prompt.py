from __future__ import annotations

from config import settings

from .memory_store import MemoryStore, memory_store
from .profile_builder import ProfileBuilder, profile_builder
from .profile_store import ProfileStore, profile_store
from .schemas import ProfileContextResult


class ProfilePromptBuilder:
    """Build profile context text for LLM prompt injection."""

    def __init__(
        self,
        *,
        store: ProfileStore | None = None,
        memories: MemoryStore | None = None,
        builder: ProfileBuilder | None = None,
    ) -> None:
        self.store = store or profile_store
        self.memories = memories or memory_store
        self.builder = builder or profile_builder

    def build_for_user(self, *, user_id: str, mode_id: str | None = None) -> ProfileContextResult:
        profile = self.store.get_profile(user_id)
        if profile is None:
            return ProfileContextResult(context="", chars=0, user_id=user_id)
        recent_events = self.memories.read_events(user_id, include_summarized=True)[-5:]
        context = self.builder.build_context(
            profile=profile,
            recent_events=recent_events,
            mode_id=mode_id,
            max_chars=settings.profile_context_max_chars,
        )
        return ProfileContextResult(context=context, chars=len(context), user_id=user_id)


profile_prompt_builder = ProfilePromptBuilder()
