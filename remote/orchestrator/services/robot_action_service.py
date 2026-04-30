from contracts.schemas import EmotionResult, RobotAction

from logging_utils import log_event
from services.mode_policy import ModePolicy, get_mode_policy


class RobotActionService:
    def for_mode_switch(self, mode: str | ModePolicy) -> RobotAction:
        policy = mode if isinstance(mode, ModePolicy) else get_mode_policy(mode)
        action = RobotAction(
            expression=policy.switch_expression,
            motion=policy.switch_motion,
            speech_style=policy.speech_style,
            priority="normal",
        )
        self._log_action(policy, "mode_switch", action)
        return action

    def for_chat(self, mode: str | ModePolicy, emotion: EmotionResult) -> RobotAction:
        policy = mode if isinstance(mode, ModePolicy) else get_mode_policy(mode)
        expression, motion = self._emotion_style(policy, emotion.label)
        action = RobotAction(
            expression=expression,
            motion=motion,
            speech_style=policy.speech_style,
            priority="normal",
        )
        self._log_action(policy, emotion.label, action)
        return action

    def _emotion_style(self, policy: ModePolicy, emotion_label: str) -> tuple[str, str]:
        if emotion_label in {"tired", "sad", "anxious"}:
            return "comfort", "slow_nod"
        if emotion_label == "happy":
            return "happy", "happy_nod"
        if policy.mode_id == "care":
            return "comfort", "slow_nod"
        if policy.mode_id == "accompany":
            return "neutral", "center"
        if policy.mode_id == "learning":
            return "listening", "center"
        if policy.mode_id == "game":
            return "happy", "happy_nod"
        return "neutral", "center"

    def _log_action(self, policy: ModePolicy, emotion_label: str, action: RobotAction) -> None:
        log_event(
            "robot_action_selected",
            mode=policy.mode_id,
            emotion_label=emotion_label,
            expression=action.expression,
            motion=action.motion,
            speech_style=action.speech_style,
        )


robot_action_service = RobotActionService()

__all__ = ["RobotActionService", "robot_action_service"]
