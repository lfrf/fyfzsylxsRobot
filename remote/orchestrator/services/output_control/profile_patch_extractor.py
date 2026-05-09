from __future__ import annotations

import re

from .schemas import ProfilePatch


class ProfilePatchExtractor:
    """Extract structured profile patch from useful user text."""

    def extract(self, asr_text: str | None, *, memory_type: str | None = None) -> ProfilePatch:
        text = str(asr_text or "").strip()
        patch = ProfilePatch()
        if not text:
            return patch

        name = self._extract_name(text)
        if name:
            patch.display_name = name

        if any(token in text for token in ("简洁", "简短", "短一点", "回答短")):
            patch.preferences["prefers_short_replies"] = True
        if any(token in text for token in ("详细", "讲清楚", "展开讲")):
            patch.preferences["prefers_detailed_explanations"] = True

        if any(token in text for token in ("嵌入式", "考试", "复习", "课程", "学习")):
            goal = self._short_text(text, 40)
            if goal:
                patch.learning_goals.append(goal)
        for topic in ("UART", "ADC", "I2C", "SPI", "PWM", "RTOS", "Linux", "Python"):
            if topic.lower() in text.lower():
                patch.recent_topics.append(topic)

        if any(token in text for token in ("累", "疲惫", "焦虑", "担心", "难过", "孤独", "紧张")):
            patch.emotional_notes.append(self._short_text(text, 36))

        if memory_type == "preference" and not patch.preferences:
            patch.facts.append(self._short_text(text, 40))

        return patch

    def _extract_name(self, text: str) -> str | None:
        patterns = [
            r"(?:我叫|叫我|称呼我|我的名字是|你可以叫我)\s*([\u4e00-\u9fffA-Za-z0-9_-]{1,12})",
        ]
        ignored = {"开始", "聊天", "测试", "游戏", "小星"}
        for pattern in patterns:
            match = re.search(pattern, text)
            if not match:
                continue
            name = match.group(1).strip(" ，。！？,.!?")
            if name and name not in ignored:
                return name[:12]
        return None

    def _short_text(self, text: str, limit: int) -> str:
        cleaned = str(text or "").strip(" ，。！？,.!?\n\t")
        return cleaned[:limit]


profile_patch_extractor = ProfilePatchExtractor()
