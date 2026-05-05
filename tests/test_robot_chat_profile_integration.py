from contracts.schemas import RobotChatRequest, RobotInput
from clients.asr_client import ASRClient
from clients.llm_client import LLMClient, LLMResult
from clients.tts_client import TTSClient
from services.mode_manager import ModeManager
from services.profile.memory_store import MemoryStore
from services.profile.profile_store import ProfileStore
from services.profile.user_profile_service import UserProfileService
from services.robot_chat_service import RobotChatService


class SpyLLMClient(LLMClient):
    def __init__(self) -> None:
        super().__init__(use_mock=True)
        self.calls = []

    def generate_reply(self, **kwargs) -> LLMResult:
        self.calls.append(kwargs)
        return LLMResult(
            reply_text="小明，听起来你今天有点累。先喝点水，休息一会儿，我们再慢慢来。",
            source="spy",
            fallback=True,
        )


def _request(text_hint: str, *, force_summary: bool = False) -> RobotChatRequest:
    return RobotChatRequest(
        session_id="session-profile",
        turn_id="turn-profile-001",
        mode="care",
        input=RobotInput(
            type="audio_base64",
            audio_base64="UklGRiQAAABXQVZFZm10IBAAAAABAAEA",
            audio_format="wav",
            sample_rate=16000,
            channels=1,
            text_hint=text_hint,
        ),
        request_options={
            "mock_user_id": "user_test_001",
            "mock_display_name": "小明",
            "force_profile_summarize": force_summary,
        },
    )


def test_robot_chat_writes_profile_memory_and_debug(tmp_path) -> None:
    root = tmp_path / "profiles"
    profile_service = UserProfileService(store=ProfileStore(root), memories=MemoryStore(root))
    llm = SpyLLMClient()
    service = RobotChatService(
        modes=ModeManager(),
        asr=ASRClient(use_mock=True),
        llm=llm,
        tts=TTSClient(use_mock=True),
        profile_service=profile_service,
    )

    response = service.handle_chat_turn(_request("我今天有点累，想复习课程", force_summary=True))

    assert response.debug["profile"]["used"] is True
    assert response.debug["profile"]["user_id"] == "user_test_001"
    assert response.debug["profile"]["identity_source"] == "mock_user_id"
    assert response.debug["profile"]["memory_written"] is True
    assert response.debug["profile"]["summary_updated"] is True
    assert response.mode.mode_id == "care"
    assert response.tts is not None
    assert response.robot_action is not None
    assert response.debug["sources"]["llm"] == "spy"
    assert response.debug["profile"]["profile_context_chars"] > 0
    assert profile_service.store.get_profile("user_test_001") is not None
    assert profile_service.memories.memory_path("user_test_001").exists()
    profile = profile_service.store.get_profile("user_test_001")
    assert profile is not None
    assert profile.profile_summary
    assert llm.calls
    assert llm.calls[0]["user_profile_context"]
    assert "小明" in llm.calls[0]["user_profile_context"]
