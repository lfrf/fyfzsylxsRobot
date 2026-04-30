from clients.llm_client import LLMClient
from clients.rag_client import RAGClient
from services.mode_chains.router import ModeChainRouter, get_chain
from services.mode_manager import ModeManager
from services.mode_policy import get_mode_policy, normalize_mode
from services.rag_router import RagRoute
from services.robot_action_service import RobotActionService
from shared.schemas import EmotionResult


def test_normalize_mode_accepts_legacy_aliases() -> None:
    assert normalize_mode("elderly") == "care"
    assert normalize_mode("normal") == "accompany"
    assert normalize_mode("student") == "learning"
    assert normalize_mode("child") == "game"


def test_explicit_switch_commands_detect_new_modes() -> None:
    manager = ModeManager()

    assert manager.detect_switch("切换为关怀模式").target_mode == "care"
    assert manager.detect_switch("切换为陪伴模式").target_mode == "accompany"
    assert manager.detect_switch("切换为学习模式").target_mode == "learning"
    assert manager.detect_switch("切换为游戏模式").target_mode == "game"


def test_implicit_phrases_do_not_switch_modes() -> None:
    manager = ModeManager()

    for text in ("我有点累", "帮我学习", "帮我复习", "玩个游戏", "陪我聊聊天"):
        assert manager.detect_switch(text).detected is False


def test_llm_prompt_contains_mode_instructions() -> None:
    client = LLMClient(use_mock=True)

    expected_markers = {
        "care": "你现在处于“关怀模式”",
        "accompany": "你现在处于“陪伴模式”",
        "learning": "你现在处于“学习模式”",
        "game": "你现在处于“游戏模式”",
    }
    for mode_id, marker in expected_markers.items():
        policy = get_mode_policy(mode_id)
        prompt = client._build_system_prompt(policy, RagRoute(namespace=policy.rag_namespace), None)
        assert marker in prompt
        assert "【语音输出约束】" in prompt
        assert "不要使用 Markdown" in prompt
        assert f"Current robot mode: {mode_id}." in prompt


def test_llm_prompt_can_include_care_rag_context() -> None:
    client = LLMClient(use_mock=True)
    policy = get_mode_policy("care")
    rag_context = RAGClient().retrieve_context(namespace="care", query="我今天有点累")

    prompt = client._build_system_prompt(policy, RagRoute(namespace=policy.rag_namespace), rag_context)

    assert "你现在处于“关怀模式”" in prompt
    assert "Optional retrieved context:" in prompt
    assert "【来源：" in prompt
    assert "02_daily_life_reminders.md" in prompt or "05_sleep_and_rest_support.md" in prompt


def test_mode_chain_router_returns_reserved_chains() -> None:
    router = ModeChainRouter()

    for mode_id in ("care", "accompany", "learning", "game"):
        assert router.get_chain(mode_id).mode_id == mode_id
        assert get_chain(mode_id).mode_id == mode_id


def test_robot_action_service_mode_defaults() -> None:
    actions = RobotActionService()
    neutral = EmotionResult(label="neutral")

    care = actions.for_chat("care", neutral)
    accompany = actions.for_chat("accompany", neutral)
    learning = actions.for_chat("learning", neutral)
    game = actions.for_chat("game", neutral)

    assert (care.expression, care.motion, care.speech_style) == ("comfort", "slow_nod", "care_gentle")
    assert accompany.expression in {"neutral", "comfort"}
    assert accompany.speech_style == "natural_warm"
    assert (learning.expression, learning.motion, learning.speech_style) == ("listening", "center", "learning_focused")
    assert (game.expression, game.motion, game.speech_style) == ("happy", "happy_nod", "game_playful")


def test_robot_action_service_emotion_overrides() -> None:
    actions = RobotActionService()

    tired = actions.for_chat("game", EmotionResult(label="tired"))
    happy = actions.for_chat("care", EmotionResult(label="happy"))

    assert (tired.expression, tired.motion) == ("comfort", "slow_nod")
    assert (happy.expression, happy.motion) == ("happy", "happy_nod")
