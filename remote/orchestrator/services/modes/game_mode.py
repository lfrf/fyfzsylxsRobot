from __future__ import annotations

from .base import BaseModeService


class GameModeService(BaseModeService):
    mode_id = "game"
    display_name = "游戏模式"
    prompt_policy = "game_playful"
    rag_namespace = "game"
    action_style = "playful_warm"
    speech_style = "game_playful"
    confirmation_text = "好呀，已切换为游戏模式。之后我们可以玩猜谜语、词语接龙这些小游戏。"
    normal_reply = "好呀，我们可以玩一个轻松的小互动。"
    switch_expression = "happy"
    switch_motion = "happy_nod"
    instruction_filename = "game.md"
    fallback_instruction = "你处于游戏模式。当前只做轻量娱乐对话和接口预留，回复活泼、简短、有互动感。"
    switch_commands = (
        "切换为游戏模式",
        "进入游戏模式",
        "打开游戏模式",
        "启用游戏模式",
        "使用游戏模式",
    )
