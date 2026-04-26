import json

from contracts.schemas import RobotChatRequest, RobotInput
from raspirobot.remote_client import RemoteClient
from services.mode_manager import ModeManager
from services.robot_chat_service import RobotChatService


def _request(session_id: str, text_hint: str, *, mode: str = "elderly", turn_id: str = "turn-0001") -> RobotChatRequest:
    return RobotChatRequest(
        session_id=session_id,
        turn_id=turn_id,
        mode=mode,
        input=RobotInput(
            type="audio_base64",
            audio_base64="UklGRiQAAABXQVZFZm10IBAAAAABAAEA",
            audio_format="wav",
            sample_rate=16000,
            channels=1,
            text_hint=text_hint,
        ),
    )


def _payload(model):
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def test_mode_switch_to_elderly_returns_namespace_and_action() -> None:
    service = RobotChatService(modes=ModeManager())

    response = service.handle_chat_turn(_request("session-elderly", "切换为老年模式", mode="normal"))

    assert response.mode_changed is True
    assert response.mode_switch.switched is True
    assert response.mode.mode_id == "elderly"
    assert response.active_rag_namespace == "elderly_care"
    assert response.robot_action.expression
    assert response.robot_action.motion


def test_mode_switch_to_child_returns_child_namespace() -> None:
    service = RobotChatService(modes=ModeManager())

    response = service.handle_chat_turn(_request("session-child", "进入儿童模式"))

    assert response.mode_changed is True
    assert response.mode.mode_id == "child"
    assert response.active_rag_namespace == "child_companion"
    assert response.robot_action.speech_style == "child_playful"


def test_mode_switch_to_student_returns_learning_namespace() -> None:
    service = RobotChatService(modes=ModeManager())

    response = service.handle_chat_turn(_request("session-student", "学习模式"))

    assert response.mode_changed is True
    assert response.mode.mode_id == "student"
    assert response.active_rag_namespace == "student_learning"
    assert response.robot_action.speech_style == "student_focused"


def test_normal_message_after_switch_uses_stored_session_mode() -> None:
    service = RobotChatService(modes=ModeManager())

    service.handle_chat_turn(_request("session-persist", "孩子模式", mode="normal", turn_id="turn-0001"))
    response = service.handle_chat_turn(
        _request("session-persist", "今天想聊点轻松的", mode="normal", turn_id="turn-0002")
    )

    assert response.mode_changed is False
    assert response.mode.mode_id == "child"
    assert response.active_rag_namespace == "child_companion"
    assert response.robot_action.speech_style == "child_playful"


def test_robot_response_contains_no_avatar_fields() -> None:
    service = RobotChatService(modes=ModeManager())

    response = service.handle_chat_turn(_request("session-no-avatar", "普通模式"))
    payload = _payload(response)
    encoded = json.dumps(payload, ensure_ascii=False)

    for forbidden in (
        "avatar_output",
        "avatar_action",
        "viseme",
        "lip_sync",
        "video_url",
        "reply_video_url",
        "reply_video_stream_url",
    ):
        assert forbidden not in payload
        assert forbidden not in encoded


def test_remote_client_instantiates_and_builds_json_base64_payload() -> None:
    client = RemoteClient(base_url="http://127.0.0.1:19000", timeout_seconds=1)
    request = _request("session-client", "你好", turn_id="turn-client")

    payload = client.build_payload(request)

    assert client.url == "http://127.0.0.1:19000/v1/robot/chat_turn"
    assert payload["input"]["audio_base64"] == "UklGRiQAAABXQVZFZm10IBAAAAABAAEA"
    assert payload["input"]["type"] == "audio_base64"
    assert "files" not in payload
    json.dumps(payload, ensure_ascii=False)
