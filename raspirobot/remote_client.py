from typing import Protocol

from shared.schemas import (
    EmotionResult,
    ModeInfo,
    ModeSwitchResult,
    RobotAction,
    RobotChatRequest,
    RobotChatResponse,
    TTSResult,
)


class RemoteClient(Protocol):
    def chat_turn(self, request: RobotChatRequest) -> RobotChatResponse:
        ...


class MockRemoteClient:
    def chat_turn(self, request: RobotChatRequest) -> RobotChatResponse:
        mode = build_mode_info(request.mode)
        return RobotChatResponse(
            success=True,
            session_id=request.session_id,
            turn_id=request.turn_id,
            mode=mode,
            mode_switch=ModeSwitchResult(
                switched=False,
                from_mode=request.mode,
                to_mode=request.mode,
            ),
            asr_text=request.input.text_hint or "mock audio received",
            reply_text="这是机器人远端接口的 mock 回复。",
            emotion=EmotionResult(label="neutral"),
            tts=TTSResult(type="audio_url", audio_url=None, format="wav"),
            robot_action=RobotAction(
                expression="neutral",
                motion="none",
                speech_style=mode.prompt_policy,
            ),
            debug={"source": "MockRemoteClient"},
        )


def build_mode_info(mode_id: str) -> ModeInfo:
    presets = {
        "elderly": ModeInfo(
            mode_id="elderly",
            display_name="老年模式",
            prompt_policy="elderly_gentle",
            rag_namespace="elderly_companion",
            action_style="calm_supportive",
        ),
        "child": ModeInfo(
            mode_id="child",
            display_name="儿童模式",
            prompt_policy="child_playful_safe",
            rag_namespace="child_companion",
            action_style="playful_warm",
        ),
        "student": ModeInfo(
            mode_id="student",
            display_name="学生模式",
            prompt_policy="student_study_support",
            rag_namespace="student_companion",
            action_style="focused_encouraging",
        ),
        "normal": ModeInfo(
            mode_id="normal",
            display_name="普通模式",
            prompt_policy="normal_family_companion",
            rag_namespace="general_companion",
            action_style="neutral_warm",
        ),
    }
    return presets.get(mode_id, presets["elderly"])

