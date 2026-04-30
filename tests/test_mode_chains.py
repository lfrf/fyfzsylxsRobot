"""Tests for ModeChainRouter and integration with RobotChatService."""

import pytest

from clients.llm_client import LLMClient, LLMResult
from services.mode_chains.base import ModeTurnContext, ModeChainResult
from services.mode_chains.care_chain import CareModeChain
from services.mode_chains.accompany_chain import AccompanyModeChain
from services.mode_chains.learning_chain import LearningModeChain
from services.mode_chains.game_chain import GameModeChain
from services.mode_chains.router import ModeChainRouter, get_chain
from services.mode_policy import get_mode_policy
from services.rag_router import RagRoute
from services.response_policy_service import ResponsePolicyService


@pytest.fixture
def llm_client_mock() -> LLMClient:
    """Mock LLM client for testing."""
    return LLMClient(use_mock=True)


@pytest.fixture
def response_policy_service() -> ResponsePolicyService:
    """Provide ResponsePolicyService instance."""
    return ResponsePolicyService()


@pytest.fixture
def router() -> ModeChainRouter:
    """Provide ModeChainRouter instance."""
    return ModeChainRouter()


# ===== Router Tests =====


def test_router_returns_care_chain(router: ModeChainRouter) -> None:
    """Test router returns CareModeChain for care mode."""
    chain = router.get_chain("care")
    assert isinstance(chain, CareModeChain)
    assert chain.mode_id == "care"


def test_router_returns_accompany_chain(router: ModeChainRouter) -> None:
    """Test router returns AccompanyModeChain for accompany mode."""
    chain = router.get_chain("accompany")
    assert isinstance(chain, AccompanyModeChain)
    assert chain.mode_id == "accompany"


def test_router_returns_learning_chain(router: ModeChainRouter) -> None:
    """Test router returns LearningModeChain for learning mode."""
    chain = router.get_chain("learning")
    assert isinstance(chain, LearningModeChain)
    assert chain.mode_id == "learning"


def test_router_returns_game_chain(router: ModeChainRouter) -> None:
    """Test router returns GameModeChain for game mode."""
    chain = router.get_chain("game")
    assert isinstance(chain, GameModeChain)
    assert chain.mode_id == "game"


def test_get_chain_function() -> None:
    """Test module-level get_chain function."""
    chain = get_chain("care")
    assert isinstance(chain, CareModeChain)


# ===== Care Chain Tests =====


def test_care_chain_handled_true(
    llm_client_mock: LLMClient,
    response_policy_service: ResponsePolicyService,
) -> None:
    """Test care chain returns handled=True."""
    chain = CareModeChain()
    policy = get_mode_policy("care")
    context = ModeTurnContext(
        session_id="session1",
        turn_id="turn1",
        mode_id="care",
        asr_text="我有点累。",
        mode_policy=policy,
        rag_route=RagRoute(namespace="care"),
        rag_context=None,
    )
    result = chain.handle_turn(context, llm_client_mock, response_policy_service)
    assert result.handled is True
    assert result.reply_text is not None
    assert len(result.reply_text) > 0


def test_care_chain_includes_debug_info(
    llm_client_mock: LLMClient,
    response_policy_service: ResponsePolicyService,
) -> None:
    """Test care chain includes debug information."""
    chain = CareModeChain()
    policy = get_mode_policy("care")
    context = ModeTurnContext(
        session_id="session1",
        turn_id="turn1",
        mode_id="care",
        asr_text="我很孤独。",
        mode_policy=policy,
        rag_route=RagRoute(namespace="care"),
    )
    result = chain.handle_turn(context, llm_client_mock, response_policy_service)
    assert result.debug["chain"] == "care"
    assert "response_policy_changed" in result.debug
    assert "response_policy_rules" in result.debug


# ===== Accompany Chain Tests =====


def test_accompany_chain_handled_true(
    llm_client_mock: LLMClient,
    response_policy_service: ResponsePolicyService,
) -> None:
    """Test accompany chain returns handled=True."""
    chain = AccompanyModeChain()
    policy = get_mode_policy("accompany")
    context = ModeTurnContext(
        session_id="session1",
        turn_id="turn1",
        mode_id="accompany",
        asr_text="今天很无聊。",
        mode_policy=policy,
        rag_route=RagRoute(namespace="general"),
    )
    result = chain.handle_turn(context, llm_client_mock, response_policy_service)
    assert result.handled is True
    assert result.reply_text is not None


def test_accompany_chain_no_mandatory_rag(
    llm_client_mock: LLMClient,
    response_policy_service: ResponsePolicyService,
) -> None:
    """Test accompany chain works without RAG context."""
    chain = AccompanyModeChain()
    policy = get_mode_policy("accompany")
    context = ModeTurnContext(
        session_id="session1",
        turn_id="turn1",
        mode_id="accompany",
        asr_text="你好",
        mode_policy=policy,
        rag_route=RagRoute(namespace="general"),
        rag_context=None,  # Explicitly None
    )
    result = chain.handle_turn(context, llm_client_mock, response_policy_service)
    assert result.handled is True
    assert result.debug["chain"] == "accompany"


# ===== Learning Chain Tests =====


def test_learning_chain_handled_true(
    llm_client_mock: LLMClient,
    response_policy_service: ResponsePolicyService,
) -> None:
    """Test learning chain returns handled=True."""
    chain = LearningModeChain()
    policy = get_mode_policy("learning")
    context = ModeTurnContext(
        session_id="session1",
        turn_id="turn1",
        mode_id="learning",
        asr_text="帮我复习一下。",
        mode_policy=policy,
        rag_route=RagRoute(namespace="learning"),
    )
    result = chain.handle_turn(context, llm_client_mock, response_policy_service)
    assert result.handled is True
    assert result.reply_text is not None


# ===== Game Chain Tests =====


def test_game_chain_starts_choose_game_flow(
    llm_client_mock: LLMClient,
    response_policy_service: ResponsePolicyService,
) -> None:
    """Test game chain can start the choose-game flow without LLM."""
    chain = GameModeChain()
    policy = get_mode_policy("game")
    context = ModeTurnContext(
        session_id="session_game_start_chain",
        turn_id="turn1",
        mode_id="game",
        asr_text="玩个游戏。",
        mode_policy=policy,
        rag_route=RagRoute(namespace="game"),
    )
    result = chain.handle_turn(context, llm_client_mock, response_policy_service)
    assert result.handled is True
    assert result.llm_result is None
    assert "A 猜谜语" in result.reply_text
    assert result.debug.get("game_status") == "CHOOSING_GAME"


# ===== Integration Tests =====


def test_router_care_chain_full_flow(
    router: ModeChainRouter,
    llm_client_mock: LLMClient,
    response_policy_service: ResponsePolicyService,
) -> None:
    """Test full flow: router -> care chain -> result."""
    chain = router.get_chain("care")
    policy = get_mode_policy("care")
    context = ModeTurnContext(
        session_id="session1",
        turn_id="turn1",
        mode_id="care",
        asr_text="我今天很疲惫。",
        mode_policy=policy,
        rag_route=RagRoute(namespace="care"),
    )
    result = chain.handle_turn(context, llm_client_mock, response_policy_service)
    assert result.handled is True
    assert result.reply_text is not None
    assert "疲惫" in context.asr_text  # Verify input was used


def test_router_game_chain_handles_game_start(
    router: ModeChainRouter,
    llm_client_mock: LLMClient,
    response_policy_service: ResponsePolicyService,
) -> None:
    """Test game mode chain handles game start directly."""
    chain = router.get_chain("game")
    policy = get_mode_policy("game")
    context = ModeTurnContext(
        session_id="session_router_game_start",
        turn_id="turn1",
        mode_id="game",
        asr_text="玩个小游戏吧。",
        mode_policy=policy,
        rag_route=RagRoute(namespace="game"),
    )
    result = chain.handle_turn(context, llm_client_mock, response_policy_service)
    assert result.handled is True
    assert result.llm_result is None
    assert result.reply_text is not None


# ===== Context and Result Tests =====


def test_mode_turn_context_creation() -> None:
    """Test ModeTurnContext dataclass creation."""
    policy = get_mode_policy("care")
    context = ModeTurnContext(
        session_id="s1",
        turn_id="t1",
        mode_id="care",
        asr_text="test",
        mode_policy=policy,
        rag_route=RagRoute(namespace="care"),
    )
    assert context.session_id == "s1"
    assert context.turn_id == "t1"
    assert context.mode_id == "care"


def test_mode_chain_result_creation() -> None:
    """Test ModeChainResult dataclass creation."""
    result = ModeChainResult(
        handled=True,
        reply_text="测试回复",
        debug={"test": "value"},
    )
    assert result.handled is True
    assert result.reply_text == "测试回复"


def test_mode_turn_context_frozen() -> None:
    """Test ModeTurnContext is immutable (frozen)."""
    policy = get_mode_policy("care")
    context = ModeTurnContext(
        session_id="s1",
        turn_id="t1",
        mode_id="care",
        asr_text="test",
        mode_policy=policy,
    )
    with pytest.raises(Exception):  # FrozenInstanceError
        context.session_id = "s2"  # type: ignore


def test_mode_chain_result_frozen() -> None:
    """Test ModeChainResult is immutable (frozen)."""
    result = ModeChainResult(handled=True, reply_text="test")
    with pytest.raises(Exception):  # FrozenInstanceError
        result.handled = False  # type: ignore


# ===== Error Handling Tests =====


def test_care_chain_error_handling(
    response_policy_service: ResponsePolicyService,
) -> None:
    """Test care chain handles errors gracefully."""
    chain = CareModeChain()
    policy = get_mode_policy("care")
    context = ModeTurnContext(
        session_id="s1",
        turn_id="t1",
        mode_id="care",
        asr_text="test",
        mode_policy=policy,
    )
    # Pass None for llm_client to trigger error
    result = chain.handle_turn(context, None, response_policy_service)  # type: ignore
    assert result.handled is False
    assert "error" in result.debug


def test_all_chains_runnable(
    llm_client_mock: LLMClient,
    response_policy_service: ResponsePolicyService,
) -> None:
    """Test all chains can be invoked without crashing."""
    policy_care = get_mode_policy("care")
    policy_accompany = get_mode_policy("accompany")
    policy_learning = get_mode_policy("learning")
    policy_game = get_mode_policy("game")

    chains = [
        (CareModeChain(), policy_care),
        (AccompanyModeChain(), policy_accompany),
        (LearningModeChain(), policy_learning),
        (GameModeChain(), policy_game),
    ]

    for chain, policy in chains:
        context = ModeTurnContext(
            session_id="s1",
            turn_id="t1",
            mode_id=chain.mode_id,
            asr_text="测试文本",
            mode_policy=policy,
            rag_route=RagRoute(namespace=policy.rag_namespace),
        )
        result = chain.handle_turn(context, llm_client_mock, response_policy_service)
        assert isinstance(result, ModeChainResult)
        assert result.debug is not None
