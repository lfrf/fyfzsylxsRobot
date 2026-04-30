from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from .types import GameHandleResult, GameIntent, GameState, GameStatus
from .riddle_engine import riddle_engine
from .word_chain_engine import word_chain_engine
from .assets import normalize_text


class GameStateService:
    """Service for managing game state and logic."""

    # Intent detection patterns
    START_PATTERNS = {
        "开始游戏",
        "玩个游戏",
        "玩游戏",
        "来玩游戏",
        "我想玩游戏",
        "我们来开始游戏",
        "我们来玩游戏",
        "我要玩游戏",
        "开始",
    }

    EXIT_PATTERNS = {
        "退出游戏",
        "退出游戏模式",
        "不玩了",
        "我不想玩了",
        "结束游戏",
        "别玩了",
        "停止游戏",
        "回到陪伴模式",
        "我不想玩",
        "不想玩",
        "退出",
        "exit",
    }

    RIDDLE_PATTERNS = {
        "a",
        "选a",
        "选择a",
        "第一个",
        "猜谜语",
        "玩猜谜语",
        "选猜谜语",
        "选择猜谜语",
    }

    WORD_CHAIN_PATTERNS = {
        "b",
        "选b",
        "选择b",
        "第二个",
        "词语接龙",
        "接龙",
        "玩词语接龙",
        "选词语接龙",
        "选择词语接龙",
    }

    SESSION_TIMEOUT = timedelta(minutes=30)

    def __init__(self) -> None:
        self._game_states: dict[str, GameState] = {}

    def detect_start_intent(self, text: str) -> bool:
        """Detect if user wants to start a game."""
        if not text:
            return False
        normalized = normalize_text(text)
        return any(pattern in normalized for pattern in self.START_PATTERNS)

    def detect_exit_intent(self, text: str) -> bool:
        """Detect if user wants to exit game (highest priority)."""
        if not text:
            return False
        normalized = normalize_text(text)
        return any(pattern in normalized for pattern in self.EXIT_PATTERNS)

    def detect_riddle_intent(self, text: str) -> bool:
        """Detect if user chooses riddle game."""
        if not text:
            return False
        normalized = normalize_text(text)
        return any(pattern in normalized for pattern in self.RIDDLE_PATTERNS)

    def detect_word_chain_intent(self, text: str) -> bool:
        """Detect if user chooses word chain game."""
        if not text:
            return False
        normalized = normalize_text(text)
        return any(pattern in normalized for pattern in self.WORD_CHAIN_PATTERNS)

    def get_or_create_state(self, session_id: str) -> GameState:
        """Get or create game state for session."""
        if session_id not in self._game_states:
            self._game_states[session_id] = GameState(session_id=session_id)
        return self._game_states[session_id]

    def is_active(self, session_id: str) -> bool:
        """Check if game is active for session."""
        state = self.get_or_create_state(session_id)
        return state.status != GameStatus.IDLE

    def start_choosing(self, session_id: str) -> GameState:
        """Start game choosing phase."""
        state = self.get_or_create_state(session_id)
        state.status = GameStatus.CHOOSING_GAME
        state.unknown_count = 0
        state.updated_at = datetime.now()
        return state

    def reset(self, session_id: str) -> None:
        """Reset game state for session."""
        if session_id in self._game_states:
            self._game_states[session_id].reset()

    def handle_turn(
        self,
        session_id: str,
        asr_text: str,
    ) -> GameHandleResult:
        """Handle a game turn."""
        state = self.get_or_create_state(session_id)

        # Check for exit intent (highest priority)
        if self.detect_exit_intent(asr_text):
            self.reset(session_id)
            return GameHandleResult(
                handled=True,
                reply_text="好的，那我们先不玩了。已回到陪伴模式，我们可以继续聊天。",
                state=state,
                mode_update="accompany",
                debug={
                    "game_state_service": "exit_detected",
                    "intent": GameIntent.EXIT_GAME,
                },
            )

        # If not in game, cannot handle
        if state.status == GameStatus.IDLE:
            return GameHandleResult(handled=False)

        # CHOOSING_GAME state
        if state.status == GameStatus.CHOOSING_GAME:
            if self.detect_riddle_intent(asr_text):
                result = riddle_engine.start(state)
                return GameHandleResult(
                    handled=True,
                    reply_text=result.reply_text,
                    state=state,
                    debug={
                        "game_state_service": "riddle_selected",
                        "intent": GameIntent.SELECT_RIDDLE,
                    },
                )

            elif self.detect_word_chain_intent(asr_text):
                result = word_chain_engine.start(state)
                return GameHandleResult(
                    handled=True,
                    reply_text=result.reply_text,
                    state=state,
                    debug={
                        "game_state_service": "word_chain_selected",
                        "intent": GameIntent.SELECT_WORD_CHAIN,
                    },
                )

            else:
                # User input is unclear in CHOOSING_GAME
                state.unknown_count += 1

                if state.unknown_count > 2:
                    # Auto exit after 2+ unknown inputs
                    self.reset(session_id)
                    return GameHandleResult(
                        handled=True,
                        reply_text="我好像没听清你的选择。那我们先结束游戏吧，回到陪伴模式。有什么我可以帮你的吗？",
                        state=state,
                        mode_update="accompany",
                        debug={
                            "game_state_service": "auto_exit",
                            "reason": "unknown_count_exceeded",
                        },
                    )

                return GameHandleResult(
                    handled=True,
                    reply_text="我还没听清。你可以说 A 猜谜语，或者 B 词语接龙。",
                    state=state,
                    debug={
                        "game_state_service": "unclear_choice",
                        "unknown_count": state.unknown_count,
                    },
                )

        # RIDDLE_WAITING_ANSWER state
        elif state.status == GameStatus.RIDDLE_WAITING_ANSWER:
            result = riddle_engine.handle_answer(state, asr_text)
            return GameHandleResult(
                handled=True,
                reply_text=result.reply_text,
                state=state,
                debug={
                    "game_state_service": "riddle_answer",
                    **result.debug,
                },
            )

        # WORD_CHAIN_WAITING_ANSWER state
        elif state.status == GameStatus.WORD_CHAIN_WAITING_ANSWER:
            result = word_chain_engine.handle_answer(state, asr_text)
            return GameHandleResult(
                handled=True,
                reply_text=result.reply_text,
                state=state,
                debug={
                    "game_state_service": "word_chain_answer",
                    **result.debug,
                },
            )

        return GameHandleResult(handled=False)


# Global singleton instance
game_state_service = GameStateService()
