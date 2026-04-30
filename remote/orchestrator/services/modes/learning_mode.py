from __future__ import annotations

from .base import BaseModeService


class LearningModeService(BaseModeService):
    mode_id = "learning"
    display_name = "学习模式"
    prompt_policy = "learning_focused"
    rag_namespace = "learning"
    action_style = "focused_encouraging"
    speech_style = "learning_focused"
    confirmation_text = "好的，已切换为学习模式。我会更有条理地帮你学习和复习。"
    normal_reply = "收到。我们可以一步一步把问题理清楚。"
    switch_expression = "listening"
    switch_motion = "center"
    instruction_filename = "learning.md"
    fallback_instruction = "你处于学习模式。帮助用户拆解学习任务，解释概念，回复清晰、有条理、不要太长。"
    switch_commands = (
        "切换为学习模式",
        "进入学习模式",
        "打开学习模式",
        "启用学习模式",
        "使用学习模式",
        "切换为学生模式",
        "进入学生模式",
    )
