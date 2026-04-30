"""Tests for game mode state service and engines."""

import pytest

from services.games.types import GameStatus, GameType, GameIntent
from services.games.game_state_service import GameStateService
from services.games.riddle_engine import RiddleEngine
from services.games.word_chain_engine import WordChainEngine


@pytest.fixture
def game_service() -> GameStateService:
    """Provide GameStateService instance."""
    return GameStateService()


@pytest.fixture
def riddle_engine_instance() -> RiddleEngine:
    """Provide RiddleEngine instance."""
    return RiddleEngine()


@pytest.fixture
def word_chain_engine_instance() -> WordChainEngine:
    """Provide WordChainEngine instance."""
    return WordChainEngine()


# ===== Intent Detection Tests =====


def test_detect_start_intent_variations(game_service: GameStateService) -> None:
    """Test detection of game start intent."""
    assert game_service.detect_start_intent("开始游戏")
    assert game_service.detect_start_intent("玩个游戏")
    assert game_service.detect_start_intent("我们来玩游戏")
    assert not game_service.detect_start_intent("你好")


def test_detect_exit_intent_variations(game_service: GameStateService) -> None:
    """Test detection of game exit intent."""
    assert game_service.detect_exit_intent("退出游戏")
    assert game_service.detect_exit_intent("不玩了")
    assert game_service.detect_exit_intent("我不想玩了")
    assert game_service.detect_exit_intent("结束游戏")
    assert not game_service.detect_exit_intent("继续玩")


def test_detect_riddle_intent_variations(game_service: GameStateService) -> None:
    """Test detection of riddle game selection."""
    assert game_service.detect_riddle_intent("a")
    assert game_service.detect_riddle_intent("A")
    assert game_service.detect_riddle_intent("诶")
    assert game_service.detect_riddle_intent("欸")
    assert game_service.detect_riddle_intent("哎")
    assert game_service.detect_riddle_intent("选a")
    assert game_service.detect_riddle_intent("选择A")
    assert game_service.detect_riddle_intent("猜谜语")
    assert game_service.detect_riddle_intent("第一")
    assert game_service.detect_riddle_intent("1")
    assert not game_service.detect_riddle_intent("b")


def test_detect_word_chain_intent_variations(game_service: GameStateService) -> None:
    """Test detection of word chain game selection."""
    assert game_service.detect_word_chain_intent("b")
    assert game_service.detect_word_chain_intent("B")
    assert game_service.detect_word_chain_intent("比")
    assert game_service.detect_word_chain_intent("选b")
    assert game_service.detect_word_chain_intent("选择B")
    assert game_service.detect_word_chain_intent("词语接龙")
    assert game_service.detect_word_chain_intent("第二")
    assert game_service.detect_word_chain_intent("2")
    assert not game_service.detect_word_chain_intent("a")


# ===== Game State Management Tests =====


def test_start_choosing_state(game_service: GameStateService) -> None:
    """Test starting game choosing phase."""
    session_id = "test_session_1"
    state = game_service.start_choosing(session_id)
    assert state.status == GameStatus.CHOOSING_GAME
    assert state.unknown_count == 0


def test_is_active_idle_state(game_service: GameStateService) -> None:
    """Test is_active returns False for idle state."""
    session_id = "test_session_2"
    assert not game_service.is_active(session_id)


def test_is_active_choosing_state(game_service: GameStateService) -> None:
    """Test is_active returns True for active game."""
    session_id = "test_session_3"
    game_service.start_choosing(session_id)
    assert game_service.is_active(session_id)


def test_reset_game_state(game_service: GameStateService) -> None:
    """Test resetting game state."""
    session_id = "test_session_4"
    game_service.start_choosing(session_id)
    assert game_service.is_active(session_id)
    game_service.reset(session_id)
    assert not game_service.is_active(session_id)


# ===== Game Turn Handling Tests =====


def test_handle_turn_exit_intent(game_service: GameStateService) -> None:
    """Test handling exit intent during game."""
    session_id = "test_session_5"
    game_service.start_choosing(session_id)

    result = game_service.handle_turn(session_id, "不玩了")
    assert result.handled
    assert result.mode_update == "care"
    assert "不玩了" in result.reply_text or "回到关怀模式" in result.reply_text


def test_handle_turn_riddle_selection(game_service: GameStateService) -> None:
    """Test selecting riddle game."""
    session_id = "test_session_6"
    game_service.start_choosing(session_id)

    result = game_service.handle_turn(session_id, "猜谜语")
    assert result.handled
    assert "第1题" in result.reply_text or "第一题" in result.reply_text


def test_handle_turn_word_chain_selection(game_service: GameStateService) -> None:
    """Test selecting word chain game."""
    session_id = "test_session_7"
    game_service.start_choosing(session_id)

    result = game_service.handle_turn(session_id, "词语接龙")
    assert result.handled
    assert "天空" in result.reply_text


def test_handle_turn_unclear_input_in_choosing(game_service: GameStateService) -> None:
    """Test unclear input in choosing state."""
    session_id = "test_session_8"
    game_service.start_choosing(session_id)

    result = game_service.handle_turn(session_id, "随便说点什么")
    assert result.handled
    assert "没听清" in result.reply_text or "听不清" in result.reply_text


def test_handle_turn_auto_exit_after_unknown(game_service: GameStateService) -> None:
    """Test auto exit after 2+ unknown inputs."""
    session_id = "test_session_9"
    game_service.start_choosing(session_id)

    # First unknown input
    result1 = game_service.handle_turn(session_id, "随便")
    assert result1.handled
    assert "没听清" in result1.reply_text or "听不清" in result1.reply_text

    # Second unknown input
    result2 = game_service.handle_turn(session_id, "再说点什么")
    assert result2.handled
    assert "没听清" in result2.reply_text or "听不清" in result2.reply_text

    # Third unknown input - should auto exit to care
    result3 = game_service.handle_turn(session_id, "其他内容")
    assert result3.handled
    assert result3.mode_update == "care"


def test_handle_turn_direct_riddle_selection_from_idle(game_service: GameStateService) -> None:
    """Test direct A selection starts riddle even if game state is idle."""
    result = game_service.handle_turn("test_session_direct_a", "A")

    assert result.handled
    assert result.state is not None
    assert result.state.status == GameStatus.RIDDLE_WAITING_ANSWER
    assert "第1题" in result.reply_text or "第一题" in result.reply_text


def test_handle_turn_direct_word_chain_selection_from_idle(game_service: GameStateService) -> None:
    """Test direct B selection starts word chain even if game state is idle."""
    result = game_service.handle_turn("test_session_direct_b", "B")

    assert result.handled
    assert result.state is not None
    assert result.state.status == GameStatus.WORD_CHAIN_WAITING_ANSWER
    assert "天空" in result.reply_text


def test_handle_turn_not_in_game(game_service: GameStateService) -> None:
    """Test handle_turn when not in game."""
    session_id = "test_session_10"
    result = game_service.handle_turn(session_id, "任何内容")
    assert not result.handled


# ===== Riddle Engine Tests =====


def test_riddle_start(riddle_engine_instance: RiddleEngine) -> None:
    """Test starting riddle game."""
    from services.games.types import GameState
    state = GameState(session_id="test_riddle_1")

    result = riddle_engine_instance.start(state)
    assert result.handled
    assert state.game_type == GameType.RIDDLE
    assert state.status == GameStatus.RIDDLE_WAITING_ANSWER
    assert state.round_index == 1
    assert state.current_prompt is not None


def test_riddle_correct_answer(riddle_engine_instance: RiddleEngine) -> None:
    """Test correct answer in riddle game."""
    from services.games.types import GameState
    state = GameState(session_id="test_riddle_2")

    # Start game
    riddle_engine_instance.start(state)
    original_answer = state.expected_answer

    # Answer correctly
    result = riddle_engine_instance.handle_answer(state, original_answer)
    assert result.handled
    assert state.score == 1
    assert "答对" in result.reply_text


def test_riddle_wrong_then_hint(riddle_engine_instance: RiddleEngine) -> None:
    """Test wrong answer triggers hint."""
    from services.games.types import GameState
    state = GameState(session_id="test_riddle_3")

    # Start game
    riddle_engine_instance.start(state)

    # Wrong answer first time
    result = riddle_engine_instance.handle_answer(state, "错误答案")
    assert result.handled
    assert "提示" in result.reply_text


def test_riddle_max_rounds(riddle_engine_instance: RiddleEngine) -> None:
    """Test riddle game reaches max rounds."""
    from services.games.types import GameState
    state = GameState(session_id="test_riddle_4")

    # Start game and answer correctly 3 times
    riddle_engine_instance.start(state)
    for i in range(riddle_engine_instance.MAX_ROUNDS):
        answer = state.expected_answer
        result = riddle_engine_instance.handle_answer(state, answer)
        if i < riddle_engine_instance.MAX_ROUNDS - 1:
            assert result.handled
            assert state.score == i + 1


# ===== Word Chain Engine Tests =====


def test_word_chain_start(word_chain_engine_instance: WordChainEngine) -> None:
    """Test starting word chain game."""
    from services.games.types import GameState
    state = GameState(session_id="test_wc_1")

    result = word_chain_engine_instance.start(state)
    assert result.handled
    assert state.game_type == GameType.WORD_CHAIN
    assert state.status == GameStatus.WORD_CHAIN_WAITING_ANSWER
    assert state.current_word == "天空"
    assert "天空" in result.reply_text


def test_word_chain_correct_answer(word_chain_engine_instance: WordChainEngine) -> None:
    """Test correct answer in word chain game."""
    from services.games.types import GameState
    state = GameState(session_id="test_wc_2")

    # Start game
    word_chain_engine_instance.start(state)

    # Answer correctly (word starting with '空')
    result = word_chain_engine_instance.handle_answer(state, "空气")
    assert result.handled
    assert state.score == 1
    assert "好接" in result.reply_text or "继续" in result.reply_text


def test_word_chain_wrong_connection(word_chain_engine_instance: WordChainEngine) -> None:
    """Test wrong connection in word chain."""
    from services.games.types import GameState
    state = GameState(session_id="test_wc_3")

    word_chain_engine_instance.start(state)

    # Wrong word (doesn't start with '空')
    result = word_chain_engine_instance.handle_answer(state, "月亮")
    assert result.handled
    assert state.score == 0
    assert "不对" in result.reply_text or "应该" in result.reply_text


def test_word_chain_repeated_word(word_chain_engine_instance: WordChainEngine) -> None:
    """Test repeated word detection."""
    from services.games.types import GameState
    state = GameState(session_id="test_wc_4")

    word_chain_engine_instance.start(state)
    state.history.append("天空")

    # Try to repeat
    result = word_chain_engine_instance.handle_answer(state, "天空")
    assert result.handled
    assert "已经玩过" in result.reply_text


# ===== Integration Tests =====


def test_game_flow_riddle_game(game_service: GameStateService) -> None:
    """Test complete riddle game flow."""
    session_id = "test_flow_riddle"

    # Start choosing
    game_service.start_choosing(session_id)

    # Select riddle
    result = game_service.handle_turn(session_id, "猜谜语")
    assert result.handled
    assert "第1题" in result.reply_text or "第一题" in result.reply_text


def test_game_flow_word_chain_game(game_service: GameStateService) -> None:
    """Test complete word chain game flow."""
    session_id = "test_flow_wc"

    # Start choosing
    game_service.start_choosing(session_id)

    # Select word chain
    result = game_service.handle_turn(session_id, "词语接龙")
    assert result.handled
    assert "天空" in result.reply_text
