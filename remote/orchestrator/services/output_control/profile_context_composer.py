from __future__ import annotations

from typing import Any

from config import settings
from logging_utils import log_event


class ProfileContextComposer:
    """Compose compact profile context without raw memory dumps."""

    def compose(
        self,
        *,
        profile: Any,
        recent_memories: list[Any] | None = None,
        current_text: str = "",
        mode_id: str | None = None,
        max_chars: int | None = None,
    ) -> str:
        max_chars = max_chars or settings.profile_context_max_chars
        recent_memories = recent_memories or []
        lines = ["当前用户画像："]
        display_name = getattr(profile, "display_name", None)
        if display_name:
            lines.append(f"- 昵称：{display_name}")
        preferences = getattr(profile, "preferences", {}) or {}
        interaction_style = getattr(profile, "interaction_style", {}) or {}
        preference_parts = self._preference_parts(preferences, interaction_style)
        if preference_parts:
            lines.append("- 偏好：" + "；".join(preference_parts[:4]))
        learning_goals = list(getattr(profile, "learning_goals", []) or [])
        recent_topics = list(getattr(profile, "recent_topics", []) or [])
        topic_parts = learning_goals[-3:] + recent_topics[-4:]
        if topic_parts:
            lines.append("- 近期学习/生活主题：" + "；".join(self._dedupe(topic_parts)[:5]))
        emotional_notes = list(getattr(profile, "emotional_notes", []) or [])
        if emotional_notes:
            lines.append("- 近期状态：" + "；".join(emotional_notes[-3:]))

        relevant = self._relevant_memory_hint(recent_memories, current_text)
        if relevant:
            lines.append(f"- 本轮相关提示：{relevant}")
        elif mode_id == "care":
            lines.append("- 本轮提示：如果用户表达疲惫或压力，先降低压力，不要催促。")

        lines.append("使用方式：自然参考，不要提到数据库、画像或内部系统。")
        context = self._truncate("\n".join(lines), max_chars)
        log_event(
            "profile_context_composed",
            user_id=getattr(profile, "user_id", None),
            mode_id=mode_id,
            context_chars=len(context),
            recent_memory_count=len(recent_memories),
        )
        return context

    def _preference_parts(self, preferences: dict, interaction_style: dict) -> list[str]:
        parts = []
        merged = {**preferences, **interaction_style}
        if merged.get("prefers_short_replies"):
            parts.append("喜欢简洁回答")
        if merged.get("prefers_detailed_explanations"):
            parts.append("需要时喜欢详细解释")
        if merged.get("likes_games"):
            parts.append("喜欢轻量小游戏")
        return parts

    def _relevant_memory_hint(self, recent_memories: list[Any], current_text: str) -> str | None:
        useful = []
        for event in reversed(recent_memories):
            memory_type = getattr(event, "memory_type", "")
            if memory_type == "noise":
                continue
            text = str(getattr(event, "asr_text", "") or "").strip()
            if not text:
                continue
            if any(token in text for token in ("学习", "考试", "UART", "ADC", "嵌入式", "累", "焦虑", "担心")):
                useful.append(text[:40])
            if useful:
                break
        return useful[0] if useful else None

    def _dedupe(self, items: list[str]) -> list[str]:
        result = []
        for item in items:
            text = str(item or "").strip()
            if text and text not in result:
                result.append(text)
        return result

    def _truncate(self, text: str, max_chars: int) -> str:
        if len(text) <= max_chars:
            return text
        return text[: max(0, max_chars - 1)].rstrip() + "…"


profile_context_composer = ProfileContextComposer()
