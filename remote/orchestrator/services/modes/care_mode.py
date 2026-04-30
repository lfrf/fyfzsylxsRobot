from __future__ import annotations

from .base import BaseModeService


class CareModeService(BaseModeService):
    mode_id = "care"
    display_name = "关怀模式"
    prompt_policy = "care_gentle"
    rag_namespace = "care"
    action_style = "calm_supportive"
    speech_style = "care_gentle"
    confirmation_text = "好的，已切换为关怀模式。我会说得慢一点、温和一点，陪你慢慢聊。"
    normal_reply = "我听到了。我们慢慢说，我会陪着你。"
    switch_expression = "comfort"
    switch_motion = "slow_nod"
    instruction_filename = "care.md"
    fallback_instruction = "你处于关怀模式。回复要短、温和、慢一点，先共情，再给轻量建议。"
    switch_commands = (
        "切换为关怀模式",
        "进入关怀模式",
        "打开关怀模式",
        "启用关怀模式",
        "使用关怀模式",
        "切换为老年模式",
        "进入老年模式",
    )
