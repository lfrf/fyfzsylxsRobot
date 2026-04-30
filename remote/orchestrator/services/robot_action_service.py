from contracts.schemas import EmotionResult, RobotAction

from services.mode_policy import ModePolicy, get_mode_policy


class RobotActionService:
    def for_mode_switch(self, mode: str | ModePolicy) -> RobotAction:
        policy = mode if isinstance(mode, ModePolicy) else get_mode_policy(mode)
        return RobotAction(
            expression=policy.switch_expression,
            motion=policy.switch_motion,
            speech_style=policy.speech_style,
            priority="normal",
        )

    def for_chat(self, mode: str | ModePolicy, emotion: EmotionResult) -> RobotAction:
        policy = mode if isinstance(mode, ModePolicy) else get_mode_policy(mode)
        expression, motion = self._emotion_style(policy, emotion.label)
        return RobotAction(
            expression=expression,
            motion=motion,
            speech_style=policy.speech_style,
            priority="normal",
        )

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


robot_action_service = RobotActionService()

__all__ = ["RobotActionService", "robot_action_service"]
