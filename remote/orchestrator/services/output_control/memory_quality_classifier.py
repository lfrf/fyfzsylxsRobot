from __future__ import annotations

from logging_utils import log_event

from .profile_patch_extractor import profile_patch_extractor
from .schemas import MemoryQualityResult


class MemoryQualityClassifier:
    """Classify whether a turn should become long-term profile memory."""

    NOISE_TOKENS = (
        "测试",
        "喂喂",
        "能听见",
        "听得见",
        "启动",
        "麦克风",
        "看得见",
        "你能听见我",
    )
    SHORT_NOISE = {"嗯", "啊", "呃", "哦", "额", "喂", "好", "行"}

    def classify(
        self,
        asr_text: str | None,
        reply_text: str = "",
        mode_id: str = "",
        emotion: str | None = None,
    ) -> MemoryQualityResult:
        text = str(asr_text or "").strip()
        compact = text.replace("。", "").replace("，", "").replace(",", "").replace(" ", "")

        if not compact:
            result = MemoryQualityResult(
                memory_type="noise",
                importance=0.0,
                should_write_memory=False,
                should_update_profile=False,
                noise_reason="empty",
            )
            self._log(text, result)
            return result
        if compact in self.SHORT_NOISE or (len(compact) < 3 and not self._has_profile_signal(compact)):
            result = MemoryQualityResult(
                memory_type="noise",
                importance=0.05,
                should_write_memory=False,
                should_update_profile=False,
                noise_reason="short_filler",
            )
            self._log(text, result)
            return result
        if any(token in text for token in self.NOISE_TOKENS):
            result = MemoryQualityResult(
                memory_type="noise",
                importance=0.1,
                should_write_memory=False,
                should_update_profile=False,
                noise_reason="test_or_device_check",
            )
            self._log(text, result)
            return result

        memory_type = "conversation_event"
        importance = 0.35
        should_update_profile = False
        if any(token in text for token in ("我叫", "叫我", "称呼我", "我的名字是")):
            memory_type = "identity"
            importance = 0.9
            should_update_profile = True
        elif any(token in text for token in ("喜欢", "不喜欢", "简洁", "简短", "详细", "短一点")):
            memory_type = "preference"
            importance = 0.75
            should_update_profile = True
        elif any(token in text for token in ("学习", "复习", "考试", "嵌入式", "UART", "ADC", "课程", "作业")):
            memory_type = "learning_goal"
            importance = 0.8
            should_update_profile = True
        elif any(token in text for token in ("累", "焦虑", "担心", "难过", "孤独", "紧张", "疲惫")):
            memory_type = "emotional_state"
            importance = 0.65
            should_update_profile = True

        patch = profile_patch_extractor.extract(text, memory_type=memory_type)
        result = MemoryQualityResult(
            memory_type=memory_type,
            importance=importance,
            should_write_memory=True,
            should_update_profile=should_update_profile or not patch.is_empty(),
            extracted={"profile_patch": patch.to_dict()},
        )
        self._log(text, result)
        return result

    def _has_profile_signal(self, text: str) -> bool:
        return any(token in text for token in ("叫", "名", "学", "累"))

    def _log(self, text: str, result: MemoryQualityResult) -> None:
        log_event(
            "memory_quality_classified",
            asr_text=text[:80],
            memory_type=result.memory_type,
            importance=result.importance,
            should_write_memory=result.should_write_memory,
            should_update_profile=result.should_update_profile,
            noise_reason=result.noise_reason,
        )


memory_quality_classifier = MemoryQualityClassifier()
