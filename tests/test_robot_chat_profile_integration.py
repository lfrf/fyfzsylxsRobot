from contracts.schemas import RobotChatRequest, RobotInput
from clients.asr_client import ASRClient
from clients.llm_client import LLMClient
from clients.tts_client import TTSClient
from services.mode_manager import ModeManager
from services.profile.memory_store import MemoryStore
from services.profile.profile_store import ProfileStore
from services.profile.user_profile_service import UserProfileService
from services.robot_chat_service import RobotChatService


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
    service = RobotChatService(
        modes=ModeManager(),
        asr=ASRClient(use_mock=True),
        llm=LLMClient(use_mock=True),
        tts=TTSClient(use_mock=True),
        profile_service=profile_service,
    )

    response = service.handle_chat_turn(_request("我今天有点累，想复习课程", force_summary=True))

    assert response.debug["profile"]["used"] is True
    assert response.debug["profile"]["user_id"] == "user_test_001"
    assert response.debug["profile"]["identity_source"] == "mock_user_id"
    assert response.debug["profile"]["memory_written"] is True
    assert response.debug["profile"]["summary_updated"] is True
    assert profile_service.memories.memory_path("user_test_001").exists()
