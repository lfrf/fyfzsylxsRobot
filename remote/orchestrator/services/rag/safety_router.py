from services.rag.contracts import SafetyRoute


HIGH_RISK_PATTERNS = [
    "不想活",
    "活着没意义",
    "轻生",
    "自杀",
    "伤害自己",
    "自残",
    "结束生命",
    "控制不住想伤人",
    "想伤人",
    "很多天没睡",
    "几天没睡",
    "停不下来",
]

SUPPORT_TOPIC_KEYWORDS = {
    "anxiety": ["焦虑", "紧张", "担心", "恐慌", "心慌", "不安", "害怕"],
    "depression": ["抑郁", "低落", "难过", "没兴趣", "无意义", "绝望", "不开心"],
    "bipolar_risk": ["亢奋", "躁", "双相", "情绪波动", "精力特别旺", "睡很少也不困"],
    "sleep": ["失眠", "睡不着", "早醒", "睡眠", "熬夜", "睡很少", "睡得少", "不困"],
    "stress": ["压力", "崩溃", "撑不住", "累", "学业", "工作"],
    "emotion_regulation": ["情绪", "烦躁", "调节", "放松", "呼吸"],
    "elderly_support": ["孤独", "老人", "陪伴", "家属", "照护"],
}


class SafetyRouter:
    def route(
        self,
        text: str,
        *,
        speech_tags: list[str] | None = None,
        vision_tags: list[str] | None = None,
        emotion_tags: list[str] | None = None,
    ) -> SafetyRoute:
        normalized = (text or "").lower()
        if self._contains_any(normalized, HIGH_RISK_PATTERNS):
            return SafetyRoute(
                label="risk_escalation",
                risk_level="high",
                topics=["escalation", "depression", "bipolar_risk", "sleep"],
                source_levels=["safety", "core", "dialogue"],
                should_retrieve=True,
                reason="high_risk_phrase",
            )

        topics = self._resolve_topics(normalized, speech_tags or [], vision_tags or [], emotion_tags or [])
        if topics:
            return SafetyRoute(
                label="support",
                risk_level="medium" if {"depression", "bipolar_risk"} & set(topics) else "low",
                topics=topics,
                source_levels=["core", "dialogue"],
                should_retrieve=True,
                reason="psychological_support_topic",
            )

        return SafetyRoute(
            label="normal",
            risk_level="low",
            topics=[],
            source_levels=["persona"],
            should_retrieve=False,
            reason="no_psychological_topic_detected",
        )

    def _resolve_topics(
        self,
        text: str,
        speech_tags: list[str],
        vision_tags: list[str],
        emotion_tags: list[str],
    ) -> list[str]:
        topics: list[str] = []
        for topic, keywords in SUPPORT_TOPIC_KEYWORDS.items():
            if self._contains_any(text, keywords):
                topics.append(topic)

        tags = {tag.lower() for tag in [*speech_tags, *vision_tags, *emotion_tags] if tag}
        if {"agitated", "tense"} & tags and "anxiety" not in topics:
            topics.append("anxiety")
        if {"sad", "fatigued"} & tags and "depression" not in topics:
            topics.append("depression")
        if {"hesitant", "calm"} & tags and "emotion_regulation" not in topics:
            topics.append("emotion_regulation")
        return topics

    def _contains_any(self, text: str, patterns: list[str]) -> bool:
        return any(pattern.lower() in text for pattern in patterns)


safety_router = SafetyRouter()
