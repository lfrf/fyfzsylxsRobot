from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass
class OutputControlPlan:
    mode_id: str
    strategy_id: str | None = None
    emotion_label: str | None = None
    risk_level: str = "low"
    reply_goal: str = ""
    prompt_hints: list[str] = field(default_factory=list)
    avoid_phrases: list[str] = field(default_factory=list)
    avoid_strategy_ids: list[str] = field(default_factory=list)
    rag_guidance: str | None = None
    profile_context: str | None = None
    debug: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_prompt_context(self) -> str:
        lines = [
            "Output control guidance:",
            f"- mode_id: {self.mode_id}",
        ]
        if self.strategy_id:
            lines.append(f"- strategy_id: {self.strategy_id}")
        if self.emotion_label:
            lines.append(f"- emotion_label: {self.emotion_label}")
        lines.append(f"- risk_level: {self.risk_level}")
        if self.reply_goal:
            lines.append(f"- reply_goal: {self.reply_goal}")
        if self.prompt_hints:
            lines.append("- prompt_hints: " + "；".join(self.prompt_hints[:4]))
        if self.avoid_phrases:
            lines.append("- avoid_phrases: " + "；".join(self.avoid_phrases[:8]))
        if self.avoid_strategy_ids:
            lines.append("- avoid_strategy_ids: " + "；".join(self.avoid_strategy_ids[:4]))
        return "\n".join(lines)


@dataclass
class CareStrategy:
    strategy_id: str = "general_support"
    emotion_label: str = "neutral"
    risk_level: str = "low"
    reply_goal: str = "自然接住用户当前表达，给出一个轻量、低压力的回应。"
    preferred_structure: str = "接住当前表达 -> 轻量支持 -> 一个自然问题或小动作"
    avoid_default_phrases: list[str] = field(default_factory=list)
    approach_variant: str = "default"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ReplyHistoryItem:
    mode_id: str
    strategy_id: str | None
    reply_text: str
    created_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MemoryQualityResult:
    memory_type: str = "conversation_event"
    importance: float = 0.4
    should_write_memory: bool = True
    should_update_profile: bool = False
    noise_reason: str | None = None
    extracted: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ProfilePatch:
    display_name: str | None = None
    facts: list[str] = field(default_factory=list)
    preferences: dict[str, Any] = field(default_factory=dict)
    learning_goals: list[str] = field(default_factory=list)
    emotional_notes: list[str] = field(default_factory=list)
    recent_topics: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def is_empty(self) -> bool:
        return not any(
            [
                self.display_name,
                self.facts,
                self.preferences,
                self.learning_goals,
                self.emotional_notes,
                self.recent_topics,
            ]
        )
