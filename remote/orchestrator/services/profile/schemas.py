from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def safe_identifier(value: str | None, *, fallback: str = "unknown") -> str:
    text = str(value or "").strip()
    chars = []
    for char in text:
        if char.isalnum() or char in {"_", "-"}:
            chars.append(char)
        else:
            chars.append("_")
    safe = "".join(chars).strip("_")
    return safe or fallback


class UserFact(BaseModel):
    key: str
    value: str
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    updated_at: str = Field(default_factory=utc_now_iso)
    source: str = Field(default="memory_summary")


class UserProfile(BaseModel):
    user_id: str
    display_name: str = Field(default="未命名用户")
    aliases: list[str] = Field(default_factory=list)
    face_ids: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=utc_now_iso)
    last_seen_at: str | None = None
    seen_count: int = Field(default=0, ge=0)
    preferred_mode: str | None = None
    profile_summary: str = Field(default="")
    preferences: dict[str, Any] = Field(default_factory=dict)
    facts: list[UserFact] = Field(default_factory=list)
    recent_topics: list[str] = Field(default_factory=list)
    learning_goals: list[str] = Field(default_factory=list)
    emotional_notes: list[str] = Field(default_factory=list)
    interaction_style: dict[str, Any] = Field(default_factory=dict)
    privacy: dict[str, Any] = Field(
        default_factory=lambda: {
            "store_face_embedding": True,
            "store_raw_images": False,
            "consent_profile_memory": True,
        }
    )


class MemoryEvent(BaseModel):
    memory_id: str = Field(default_factory=lambda: f"mem_{uuid4().hex}")
    user_id: str
    session_id: str
    turn_id: str
    timestamp: str = Field(default_factory=utc_now_iso)
    mode: str
    asr_text: str
    reply_text: str
    emotion: str | None = None
    face_id: str | None = None
    tags: list[str] = Field(default_factory=list)
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    memory_type: str = Field(default="interaction")
    summarized: bool = False
    source: str = Field(default="robot_chat_turn")


class IdentityResolution(BaseModel):
    user_id: str
    identity_source: str
    face_id: str | None = None
    display_name: str | None = None
    is_anonymous: bool = False
    profile: UserProfile | None = None


class MemoryWriteResult(BaseModel):
    written: bool = False
    memory_id: str | None = None
    summary_updated: bool = False
    unsummarized_count: int = 0
    error: str | None = None


class ProfileContextResult(BaseModel):
    context: str = ""
    chars: int = 0
    user_id: str | None = None


class SummaryUpdateResult(BaseModel):
    updated: bool = False
    summarized_count: int = 0
    error: str | None = None
