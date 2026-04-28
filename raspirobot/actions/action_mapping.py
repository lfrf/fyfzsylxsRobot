from __future__ import annotations

from shared.schemas import RobotAction


def normalize_action(action: RobotAction) -> RobotAction:
    return RobotAction(
        expression=action.expression or "neutral",
        motion=action.motion or "none",
        speech_style=action.speech_style or "normal",
        head_target=action.head_target,
        priority=action.priority or "normal",
    )
