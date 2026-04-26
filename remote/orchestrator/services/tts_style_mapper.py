from dataclasses import asdict, dataclass


PROMPT_END = "<|endofprompt|>"
DEFAULT_STYLE = "supportive"
DEFAULT_SPEAKER_ID = "\u4e2d\u6587\u5973"  # 中文女


@dataclass(frozen=True)
class TTSStylePreset:
    instruct_text: str
    speed: float
    speaker_id: str | None = None


@dataclass(frozen=True)
class TTSRenderPlan:
    emotion_style: str
    tts_instruct_text: str
    tts_speed: float
    tts_speaker_id: str | None = None

    def to_avatar_payload(self) -> dict:
        return {
            "emotion_style": self.emotion_style,
            "tts_instruct_text": self.tts_instruct_text,
            "tts_speed": self.tts_speed,
            "tts_speaker_id": self.tts_speaker_id,
        }

    def to_dict(self) -> dict:
        return asdict(self)


def _ensure_prompt_end(text: str) -> str:
    cleaned = (text or "").strip()
    if not cleaned:
        return ""
    if PROMPT_END not in cleaned:
        return f"{cleaned}{PROMPT_END}"
    return cleaned


DEFAULT_TTS_STYLE_PRESETS: dict[str, TTSStylePreset] = {
    "gentle": TTSStylePreset(
        instruct_text=_ensure_prompt_end(
            "\u8bf7\u7528\u6e29\u67d4\u3001\u4f4e\u523a\u6fc0\u3001\u5e26\u5b89\u629a\u611f\u7684\u5973\u58f0\u6717\u8bfb\u3002"
            "\u8bed\u901f\u653e\u6162\uff0c\u505c\u987f\u66f4\u5145\u5206\u3002"
        ),
        speed=0.82,
        speaker_id=DEFAULT_SPEAKER_ID,
    ),
    "supportive": TTSStylePreset(
        instruct_text=_ensure_prompt_end(
            "\u8bf7\u7528\u6e29\u6696\u3001\u771f\u8bda\u3001\u5e26\u966a\u4f34\u611f\u7684\u5973\u58f0\u6717\u8bfb\u3002"
            "\u8bed\u6c14\u8f7b\u67d4\u4f46\u6709\u529b\u91cf\uff0c\u8ba9\u4eba\u611f\u5230\u88ab\u652f\u6301\u3002"
        ),
        speed=0.95,
        speaker_id=DEFAULT_SPEAKER_ID,
    ),
    "neutral": TTSStylePreset(
        instruct_text=_ensure_prompt_end(
            "\u8bf7\u7528\u5e73\u9759\u3001\u81ea\u7136\u7684\u4e2d\u6587\u5973\u58f0\u6717\u8bfb\uff0c\u4fdd\u6301\u4e2d\u6027\u5ba2\u89c2\u3002"
        ),
        speed=1.0,
        speaker_id=DEFAULT_SPEAKER_ID,
    ),
    "attentive": TTSStylePreset(
        instruct_text=_ensure_prompt_end(
            "\u8bf7\u7528\u8ba4\u771f\u3001\u4e13\u6ce8\u3001\u6709\u5173\u5207\u611f\u7684\u5973\u58f0\u6717\u8bfb\u3002"
            "\u8bed\u901f\u7565\u6162\uff0c\u8868\u8fbe\u7a33\u5b9a\u548c\u8010\u5fc3\u3002"
        ),
        speed=0.93,
        speaker_id=DEFAULT_SPEAKER_ID,
    ),
    "listening": TTSStylePreset(
        instruct_text=_ensure_prompt_end(
            "\u8bf7\u7528\u8f7b\u67d4\u3001\u8010\u5fc3\u3001\u503e\u542c\u611f\u660e\u663e\u7684\u5973\u58f0\u6717\u8bfb\u3002"
        ),
        speed=0.9,
        speaker_id=DEFAULT_SPEAKER_ID,
    ),
    "encouraging": TTSStylePreset(
        instruct_text=_ensure_prompt_end(
            "\u8bf7\u7528\u79ef\u6781\u3001\u660e\u4eae\u3001\u771f\u8bda\u7684\u5973\u58f0\u6717\u8bfb\uff0c\u6574\u4f53\u60c5\u7eea\u5411\u4e0a\u3002"
        ),
        speed=1.05,
        speaker_id=DEFAULT_SPEAKER_ID,
    ),
}


class TTSStyleMapper:
    def __init__(
        self,
        presets: dict[str, TTSStylePreset] | None = None,
        *,
        default_style: str = DEFAULT_STYLE,
    ) -> None:
        self._presets = presets or DEFAULT_TTS_STYLE_PRESETS
        self._default_style = default_style

    def build_plan(
        self,
        *,
        emotion_style: str | None,
        reply_text: str,
        override_instruct_text: str | None = None,
        override_speed: float | None = None,
        override_speaker_id: str | None = None,
    ) -> TTSRenderPlan:
        resolved_style = self._resolve_style(emotion_style)
        preset = self._presets[resolved_style]

        instruct_text = self._resolve_instruct_text(
            override_instruct_text=override_instruct_text,
            preset=preset,
            reply_text=reply_text,
        )
        speed = override_speed if override_speed is not None else preset.speed
        speaker_id = override_speaker_id if override_speaker_id is not None else preset.speaker_id

        return TTSRenderPlan(
            emotion_style=resolved_style,
            tts_instruct_text=instruct_text,
            tts_speed=speed,
            tts_speaker_id=speaker_id,
        )

    def _resolve_style(self, emotion_style: str | None) -> str:
        normalized = (emotion_style or "").strip().lower()
        if normalized in self._presets:
            return normalized
        return self._default_style

    def _resolve_instruct_text(
        self,
        *,
        override_instruct_text: str | None,
        preset: TTSStylePreset,
        reply_text: str,
    ) -> str:
        instruct_text = (override_instruct_text or "").strip()
        if instruct_text:
            return _ensure_prompt_end(instruct_text)

        if preset.instruct_text.strip():
            return preset.instruct_text

        return _ensure_prompt_end(
            "\u8bf7\u7528\u81ea\u7136\u3001\u6807\u51c6\u7684\u4e2d\u6587\u5973\u58f0\u6717\u8bfb\u4ee5\u4e0b\u5185\u5bb9\uff1a"
            f"{reply_text[:120]}"
        )


tts_style_mapper = TTSStyleMapper()
