import json

from clients.asr_client import ASRClient
from clients.llm_client import LLMClient
from clients.tts_client import TTSClient
from contracts.schemas import RobotChatRequest, RobotInput
from services.mode_policy import get_mode_policy
from services.rag_router import RagRoute
from services.robot_chat_service import RobotChatService


def _request(text_hint: str | None = "你好", *, session_id: str = "session-clients") -> RobotChatRequest:
    return RobotChatRequest(
        session_id=session_id,
        turn_id="turn-0001",
        mode="elderly",
        input=RobotInput(
            audio_base64="UklGRiQAAABXQVZFZm10IBAAAAABAAEA",
            audio_format="wav",
            sample_rate=16000,
            channels=2,
            text_hint=text_hint,
        ),
    )


def test_asr_client_mock_mode_uses_text_hint() -> None:
    result = ASRClient(use_mock=True).transcribe(_request("你好，测试"))

    assert result.text == "你好，测试"
    assert result.source == "text_hint"


def test_asr_client_mock_mode_without_hint_returns_placeholder() -> None:
    result = ASRClient(use_mock=True).transcribe(_request(None))

    assert result.text == "mock audio received"
    assert "mock" in result.source


def test_llm_client_mock_mode_generates_reply() -> None:
    policy = get_mode_policy("elderly")
    result = LLMClient(use_mock=True).generate_reply(
        session_id="session-llm",
        turn_id="turn-0001",
        asr_text="我今天有点累",
        mode_policy=policy,
        rag_route=RagRoute(namespace=policy.rag_namespace),
    )

    assert result.reply_text
    assert result.source == "mock"


def test_tts_client_mock_mode_returns_audio_url() -> None:
    result = TTSClient(use_mock=True).synthesize(
        text="你好",
        session_id="session-tts",
        turn_id="turn-0001",
        mode="elderly",
        speech_style="elderly_gentle",
    )

    assert result.tts.type == "audio_url"
    assert result.tts.audio_url
    assert result.tts.audio_url.startswith("mock://")


def test_robot_chat_normal_chat_uses_mock_llm_and_tts() -> None:
    service = RobotChatService(
        asr=ASRClient(use_mock=True),
        llm=LLMClient(use_mock=True),
        tts=TTSClient(use_mock=True),
    )

    response = service.handle_chat_turn(_request("你好，今天聊聊天"))

    assert response.success is True
    assert response.mode_changed is False
    assert response.asr_text == "你好，今天聊聊天"
    assert response.reply_text
    assert response.tts.audio_url
    assert response.debug["llm_source"] == "mock"
    assert response.debug["tts_source"] == "mock"


def test_robot_chat_response_contains_no_avatar_fields_after_real_layering() -> None:
    service = RobotChatService(
        asr=ASRClient(use_mock=True),
        llm=LLMClient(use_mock=True),
        tts=TTSClient(use_mock=True),
    )

    response = service.handle_chat_turn(_request("你好"))
    payload = response.model_dump() if hasattr(response, "model_dump") else response.dict()
    encoded = json.dumps(payload, ensure_ascii=False)

    for forbidden in (
        "avatar_output",
        "avatar_action",
        "viseme",
        "lip_sync",
        "video_url",
    ):
        assert forbidden not in payload
        assert forbidden not in encoded
