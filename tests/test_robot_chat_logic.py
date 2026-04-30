import json

from contracts.schemas import RobotChatRequest, RobotInput
from raspirobot.remote_client import RemoteClient
from clients.asr_client import ASRClient
from clients.llm_client import LLMClient
from clients.tts_client import TTSClient
from services.mode_manager import ModeManager
from services.robot_chat_service import RobotChatService


def _request(session_id: str, text_hint: str, *, mode: str = "care", turn_id: str = "turn-0001") -> RobotChatRequest:
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


class RaisingLLMClient:
    api_base = "mock://llm"

    def generate_reply(self, **kwargs):
        raise AssertionError("LLM should be skipped for explicit mode switches")


def _service(*, llm=None) -> RobotChatService:
    return RobotChatService(
        modes=ModeManager(),
        asr=ASRClient(use_mock=True),
        llm=llm or LLMClient(use_mock=True),
        tts=TTSClient(use_mock=True),
    )


def test_mode_switch_to_care_returns_namespace_and_action() -> None:
    service = _service()

    response = service.handle_chat_turn(_request("session-care", "切换为关怀模式", mode="accompany"))

    assert response.mode_changed is True
    assert response.mode_switch.switched is True
    assert response.mode.mode_id == "care"
    assert response.active_rag_namespace == "care"
    assert response.robot_action.expression == "comfort"
    assert response.robot_action.motion == "slow_nod"


def test_mode_switch_to_accompany_returns_general_namespace() -> None:
    service = _service()

    response = service.handle_chat_turn(_request("session-accompany", "进入陪伴模式"))

    assert response.mode_changed is True
    assert response.mode.mode_id == "accompany"
    assert response.active_rag_namespace == "general"
    assert response.robot_action.speech_style == "natural_warm"


def test_mode_switch_to_learning_returns_learning_namespace() -> None:
    service = _service()

    response = service.handle_chat_turn(_request("session-learning", "切换为学习模式"))

    assert response.mode_changed is True
    assert response.mode.mode_id == "learning"
    assert response.active_rag_namespace == "learning"
    assert response.robot_action.speech_style == "learning_focused"


def test_mode_switch_to_game_returns_game_namespace() -> None:
    service = _service()

    response = service.handle_chat_turn(_request("session-game", "进入游戏模式"))

    assert response.mode_changed is True
    assert response.mode.mode_id == "game"
    assert response.active_rag_namespace == "game"
    assert response.robot_action.speech_style == "game_playful"


def test_normal_message_after_switch_uses_stored_session_mode() -> None:
    service = _service()

    service.handle_chat_turn(_request("session-persist", "切换为游戏模式", mode="accompany", turn_id="turn-0001"))
    response = service.handle_chat_turn(
        _request("session-persist", "今天想聊点轻松的", mode="accompany", turn_id="turn-0002")
    )

    assert response.mode_changed is False
    assert response.mode.mode_id == "game"
    assert response.active_rag_namespace == "game"
    assert response.robot_action.speech_style == "game_playful"


def test_implicit_mode_phrases_do_not_switch() -> None:
    service = _service()

    for index, text in enumerate(("我有点累", "帮我学习", "帮我复习", "玩个游戏", "陪我聊聊天"), start=1):
        response = service.handle_chat_turn(
            _request("session-implicit", text, mode="care", turn_id=f"turn-{index:04d}")
        )
        assert response.mode_changed is False
        assert response.mode.mode_id == "care"


def test_care_normal_chat_uses_care_rag_context() -> None:
    service = _service()

    response = service.handle_chat_turn(_request("session-care-rag", "我今天有点累", mode="care"))

    assert response.mode_changed is False
    assert response.mode.mode_id == "care"
    assert response.active_rag_namespace == "care"
    assert response.debug["rag_context_used"] is True
    assert response.debug["rag_matched_files"]
    assert response.debug["rag_context_chars"] > 0
    assert response.debug["rag_used_default_docs"] is False
    assert response.debug["mode"]["current_mode"] == "care"
    assert response.debug["mode"]["active_rag_namespace"] == "care"


def test_mode_switch_skips_llm() -> None:
    service = _service(llm=RaisingLLMClient())

    response = service.handle_chat_turn(_request("session-skip-llm", "切换为关怀模式", mode="accompany"))

    assert response.mode_changed is True
    assert response.debug["sources"]["llm"] == "mode_switch"


def test_robot_response_contains_no_avatar_fields() -> None:
    service = _service()

    response = service.handle_chat_turn(_request("session-no-avatar", "你好"))
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
