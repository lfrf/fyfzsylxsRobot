"""Tests for GameModeChain."""

import pytest

from clients.llm_client import LLMClient
from services.mode_chains.game_chain import GameModeChain
from services.mode_chains.base import ModeTurnContext
from services.response_policy_service import ResponsePolicyService
from services.games.game_state_service import game_state_service


@pytest.fixture
def game_chain() -> GameModeChain:
    """Provide GameModeChain instance."""
    return GameModeChain()


@pytest.fixture
def llm_client() -> LLMClient:
    """Provide mock LLM client."""
    return LLMClient(use_mock=True)


@pytest.fixture
def response_policy() -> ResponsePolicyService:
    """Provide ResponsePolicyService instance."""
    return ResponsePolicyService()


# ===== Basic Chain Tests =====


def test_game_chain_mode_id(game_chain: GameModeChain) -> None:
    """Test GameModeChain has correct mode_id."""
    assert game_chain.mode_id == "game"


def test_game_chain_not_handled_when_game_idle(
    game_chain: GameModeChain,
    llm_client: LLMClient,
    response_policy: ResponsePolicyService,
) -> None:
    """Test GameModeChain returns handled=False when game not active."""
    context = ModeTurnContext(
        session_id="test_1",
        turn_id="turn_1",
        mode_id="game",
        asr_text="any text",
    )
    result = game_chain.handle_turn(context, llm_client, response_policy)
    assert result.handled is False


def test_game_chain_handled_on_game_active(
    game_chain: GameModeChain,
    llm_client: LLMClient,
    response_policy: ResponsePolicyService,
) -> None:
    """Test GameModeChain handles active game."""
    session_id = "test_2"
    game_state_service.start_choosing(session_id)

    context = ModeTurnContext(
        session_id=session_id,
        turn_id="turn_1",
        mode_id="game",
        asr_text="猜谜语",
    )
    result = game_chain.handle_turn(context, llm_client, response_policy)
    assert result.handled is True
    assert result.reply_text is not None


def test_game_chain_returns_robot_action_hint(
    game_chain: GameModeChain,
    llm_client: LLMClient,
    response_policy: ResponsePolicyService,
) -> None:
    """Test GameModeChain returns robot_action_hint."""
    session_id = "test_3"
    game_state_service.start_choosing(session_id)

    context = ModeTurnContext(
        session_id=session_id,
        turn_id="turn_1",
        mode_id="game",
        asr_text="玩猜谜语",
    )
    result = game_chain.handle_turn(context, llm_client, response_policy)
    assert result.handled is True
    assert result.robot_action_hint is not None
    assert result.robot_action_hint.get("expression") == "happy"
    assert result.robot_action_hint.get("motion") == "happy_nod"


def test_game_chain_exit_game(
    game_chain: GameModeChain,
    llm_client: LLMClient,
    response_policy: ResponsePolicyService,
) -> None:
    """Test GameModeChain handles game exit."""
    session_id = "test_4"
    game_state_service.start_choosing(session_id)

    context = ModeTurnContext(
        session_id=session_id,
        turn_id="turn_1",
        mode_id="game",
        asr_text="退出游戏",
    )
    result = game_chain.handle_turn(context, llm_client, response_policy)
    assert result.handled is True
    assert result.debug.get("mode_update") == "accompany"


def test_game_chain_debug_info(
    game_chain: GameModeChain,
    llm_client: LLMClient,
    response_policy: ResponsePolicyService,
) -> None:
    """Test GameModeChain returns debug info."""
    session_id = "test_5"
    game_state_service.start_choosing(session_id)

    context = ModeTurnContext(
        session_id=session_id,
        turn_id="turn_1",
        mode_id="game",
        asr_text="选A",
    )
    result = game_chain.handle_turn(context, llm_client, response_policy)
    assert result.debug is not None
    assert result.debug.get("chain") == "game"
    assert result.debug.get("session_id") == session_id
    assert result.debug.get("turn_id") == "turn_1"


def test_game_chain_riddle_selection(
    game_chain: GameModeChain,
    llm_client: LLMClient,
    response_policy: ResponsePolicyService,
) -> None:
    """Test GameModeChain handles riddle selection."""
    session_id = "test_6"
    game_state_service.start_choosing(session_id)

    context = ModeTurnContext(
        session_id=session_id,
        turn_id="turn_1",
        mode_id="game",
        asr_text="A",
    )
    result = game_chain.handle_turn(context, llm_client, response_policy)
    assert result.handled is True
    assert "题" in result.reply_text


def test_game_chain_word_chain_selection(
    game_chain: GameModeChain,
    llm_client: LLMClient,
    response_policy: ResponsePolicyService,
) -> None:
    """Test GameModeChain handles word chain selection."""
    session_id = "test_7"
    game_state_service.start_choosing(session_id)

    context = ModeTurnContext(
        session_id=session_id,
        turn_id="turn_1",
        mode_id="game",
        asr_text="B",
    )
    result = game_chain.handle_turn(context, llm_client, response_policy)
    assert result.handled is True
    assert "天空" in result.reply_text or "接龙" in result.reply_text


# ===== Error Handling Tests =====


def test_game_chain_error_handling(
    game_chain: GameModeChain,
    llm_client: LLMClient,
    response_policy: ResponsePolicyService,
) -> None:
    """Test GameModeChain handles errors gracefully."""
    # Create invalid context (missing required fields should not crash)
    context = ModeTurnContext(
        session_id="",
        turn_id="",
        mode_id="game",
        asr_text="",
    )
    result = game_chain.handle_turn(context, llm_client, response_policy)
    # Should fallback to handled=False on error
    assert result is not None
