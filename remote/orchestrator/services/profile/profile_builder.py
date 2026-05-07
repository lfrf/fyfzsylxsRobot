from __future__ import annotations

from collections import Counter

from .schemas import MemoryEvent, SummaryUpdateResult, UserFact, UserProfile, utc_now_iso


class ProfileBuilder:
    """Build compact profile context and deterministic profile summaries."""

    def build_context(
        self,
        *,
        profile: UserProfile,
        recent_events: list[MemoryEvent] | None = None,
        mode_id: str | None = None,
        max_chars: int = 800,
    ) -> str:
        recent_events = recent_events or []
        lines: list[str] = ["当前用户画像："]
        if profile.display_name and profile.display_name != "未命名用户":
            lines.append(f"- 用户昵称：{profile.display_name}")
        if profile.preferred_mode:
            lines.append(f"- 常用模式：{profile.preferred_mode}")
        if profile.profile_summary:
            lines.append(f"- 概要：{profile.profile_summary}")
        if profile.preferences:
            preferences = self._dict_preview(profile.preferences, limit=4)
            if preferences:
                lines.append(f"- 偏好：{preferences}")
        if profile.interaction_style:
            style = self._dict_preview(profile.interaction_style, limit=3)
            if style:
                lines.append(f"- 互动习惯：{style}")
        if profile.emotional_notes:
            lines.append(f"- 近期状态：{'；'.join(profile.emotional_notes[-3:])}")
        if profile.recent_topics:
            lines.append(f"- 近期话题：{'、'.join(profile.recent_topics[-5:])}")
        if profile.learning_goals:
            lines.append(f"- 学习目标：{'、'.join(profile.learning_goals[-4:])}")
        if profile.facts:
            facts = "；".join(f"{fact.key}：{fact.value}" for fact in profile.facts[-4:])
            lines.append(f"- 稳定信息：{facts}")
        if recent_events:
            snippets = []
            for event in recent_events[-3:]:
                text = event.asr_text.strip()
                if text:
                    snippets.append(text[:36])
            if snippets:
                lines.append(f"- 最近记忆：{'；'.join(snippets)}")
        if mode_id == "game":
            lines.append("回复要求：可轻轻参考游戏偏好，保持轻松自然。")
        else:
            lines.append("回复要求：自然参考这些信息，不要提到内部画像、数据库或记忆系统。")
        return self._truncate("\n".join(lines), max_chars)

    def summarize(self, profile: UserProfile, events: list[MemoryEvent]) -> SummaryUpdateResult:
        if not events:
            return SummaryUpdateResult(updated=False, summarized_count=0)

        for event in events:
            self._apply_event_rules(profile, event)

        self._update_preferred_mode(profile, events)
        self._update_profile_summary(profile)
        return SummaryUpdateResult(updated=True, summarized_count=len(events))

    def _apply_event_rules(self, profile: UserProfile, event: MemoryEvent) -> None:
        text = f"{event.asr_text} {event.reply_text}".strip()
        now = utc_now_iso()
        if any(token in text for token in ("累", "疲惫", "困", "没精神")):
            self._append_unique(profile.emotional_notes, "最近提到疲惫或需要休息")
        if any(token in text for token in ("开心", "高兴", "太好了")):
            self._append_unique(profile.emotional_notes, "最近表达过开心")
        if any(token in text for token in ("焦虑", "担心", "紧张")):
            self._append_unique(profile.emotional_notes, "最近有担心或紧张")
        if any(token in text for token in ("学习", "复习", "计划", "课程", "作业")):
            self._append_unique(profile.learning_goals, self._short_topic(event.asr_text))
            self._append_unique(profile.recent_topics, "学习")
        if event.mode == "game" or any(token in text for token in ("游戏", "猜谜", "接龙")):
            profile.preferences["likes_games"] = True
            self._append_unique(profile.recent_topics, "游戏")
        if "短一点" in text or "简单" in text:
            profile.interaction_style["prefers_short_replies"] = True
        if "详细" in text or "讲清楚" in text:
            profile.interaction_style["prefers_detailed_explanations"] = True
        if "我叫" in event.asr_text:
            name = event.asr_text.split("我叫", 1)[-1].strip(" ，。！？")
            if name:
                profile.display_name = name[:12]
                self._upsert_fact(profile, key="name", value=profile.display_name, updated_at=now)
        if event.mode:
            profile.preferences[f"used_mode_{event.mode}"] = profile.preferences.get(f"used_mode_{event.mode}", 0) + 1
        topic = self._short_topic(event.asr_text)
        if topic:
            self._append_unique(profile.recent_topics, topic)
        profile.last_seen_at = event.timestamp

    def _update_preferred_mode(self, profile: UserProfile, events: list[MemoryEvent]) -> None:
        mode_counts = Counter(event.mode for event in events if event.mode)
        for key, value in profile.preferences.items():
            if key.startswith("used_mode_") and isinstance(value, int):
                mode_counts[key.removeprefix("used_mode_")] += value
        if mode_counts:
            profile.preferred_mode = mode_counts.most_common(1)[0][0]

    def _update_profile_summary(self, profile: UserProfile) -> None:
        parts = []
        if profile.emotional_notes:
            parts.append(profile.emotional_notes[-1])
        if profile.learning_goals:
            parts.append(f"关注学习：{profile.learning_goals[-1]}")
        if profile.preferences.get("likes_games"):
            parts.append("喜欢轻量小游戏")
        if profile.interaction_style.get("prefers_short_replies"):
            parts.append("偏好简短回复")
        elif profile.interaction_style.get("prefers_detailed_explanations"):
            parts.append("有时需要详细解释")
        profile.profile_summary = "；".join(parts[:4])

    def _upsert_fact(self, profile: UserProfile, *, key: str, value: str, updated_at: str) -> None:
        for fact in profile.facts:
            if fact.key == key:
                fact.value = value
                fact.updated_at = updated_at
                fact.confidence = max(fact.confidence, 0.8)
                return
        profile.facts.append(UserFact(key=key, value=value, confidence=0.8, updated_at=updated_at))

    def _short_topic(self, text: str) -> str:
        cleaned = str(text or "").strip(" ，。！？\n\t")
        return cleaned[:24]

    def _append_unique(self, items: list[str], value: str, *, limit: int = 12) -> None:
        text = str(value or "").strip()
        if not text:
            return
        if text in items:
            items.remove(text)
        items.append(text)
        del items[:-limit]

    def _dict_preview(self, data: dict, *, limit: int) -> str:
        parts = []
        for key, value in list(data.items())[:limit]:
            parts.append(f"{key}={value}")
        return "，".join(parts)

    def _truncate(self, text: str, max_chars: int) -> str:
        if len(text) <= max_chars:
            return text
        return text[: max(0, max_chars - 1)].rstrip() + "…"


profile_builder = ProfileBuilder()
