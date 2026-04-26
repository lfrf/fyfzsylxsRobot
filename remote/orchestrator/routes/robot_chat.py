import sys
from pathlib import Path

from fastapi import APIRouter

SHARED_PATH_CANDIDATES = [
    Path("/shared"),
    Path(__file__).resolve().parents[3] / "shared",
]

for candidate in SHARED_PATH_CANDIDATES:
    if candidate.exists() and str(candidate) not in sys.path:
        sys.path.append(str(candidate))

from contracts.schemas import (  # noqa: E402
    EmotionResult,
    ModeInfo,
    ModeSwitchResult,
    RobotAction,
    RobotChatRequest,
    RobotChatResponse,
    TTSResult,
)

router = APIRouter()


@router.post("/v1/robot/chat_turn", response_model=RobotChatResponse)
async def robot_chat_turn(request: RobotChatRequest) -> RobotChatResponse:
    mode = _mode_info(request.mode)
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
        asr_text=request.input.text_hint or "",
        reply_text="机器人对话接口骨架已接通。后续会在这里接入 ASR、模式切换、LLM、TTS 和动作规划。",
        emotion=EmotionResult(label="neutral"),
        tts=TTSResult(type="audio_url", audio_url=None, format="wav"),
        robot_action=RobotAction(
            expression="neutral",
            motion="none",
            speech_style=mode.prompt_policy,
        ),
        debug={"source": "robot_chat_skeleton"},
    )


def _mode_info(mode_id: str) -> ModeInfo:
    modes = {
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
    return modes.get(mode_id, modes["elderly"])
