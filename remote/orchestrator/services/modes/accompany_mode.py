from __future__ import annotations

from .base import BaseModeService


class AccompanyModeService(BaseModeService):
    mode_id = "accompany"
    display_name = "陪伴模式"
    prompt_policy = "accompany_warm"
    rag_namespace = "general"
    action_style = "neutral_warm"
    speech_style = "natural_warm"
    confirmation_text = "好的，已切换为陪伴模式。我们可以自然地聊聊天。"
    normal_reply = "我在呢，我们可以慢慢聊。"
    switch_expression = "neutral"
    switch_motion = "center"
    instruction_filename = "accompany.md"
    fallback_instruction = "你处于陪伴模式。像朋友一样自然、温暖地聊天，回复短一点，适合语音播放。"
    switch_commands = (
        "切换为陪伴模式",
        "进入陪伴模式",
        "打开陪伴模式",
        "启用陪伴模式",
        "使用陪伴模式",
        "切换为普通模式",
        "进入普通模式",
    )
