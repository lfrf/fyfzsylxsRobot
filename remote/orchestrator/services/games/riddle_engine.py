from __future__ import annotations

from .types import GameHandleResult, GameState, GameStatus, GameType
from .assets import RIDDLES, normalize_text, get_random_riddle_indices


class RiddleEngine:
    """Engine for handling riddle game logic."""

    MAX_ROUNDS = 3
    MAX_ATTEMPTS_PER_RIDDLE = 2

    def start(self, state: GameState) -> GameHandleResult:
        """Start riddle game."""
        state.game_type = GameType.RIDDLE
        state.round_index = 0
        state.score = 0
        state.attempts = 0
        state.status = GameStatus.RIDDLE_WAITING_ANSWER

        result = self._load_next_riddle(state)
        return GameHandleResult(
            handled=True,
            reply_text=result,
            state=state,
            debug={
                "engine": "riddle",
                "action": "start",
                "round": state.round_index,
                "prompt": state.current_prompt,
            },
        )

    def handle_answer(self, state: GameState, user_text: str) -> GameHandleResult:
        """Handle user answer in riddle game."""
        normalized_answer = normalize_text(user_text)
        normalized_expected = normalize_text(state.expected_answer or "")
        normalized_aliases = [normalize_text(alias) for alias in (state.answer_aliases or [])]

        # Check if answer is correct
        is_correct = (
            normalized_answer == normalized_expected
            or normalized_answer in normalized_aliases
        )

        if is_correct:
            state.score += 1
            state.attempts = 0
            reply = f"恭喜你，答对了！正确答案就是{state.expected_answer}。\n"

            if state.round_index >= self.MAX_ROUNDS - 1:
                # Game finished
                reply += f"我们已经完成了{self.MAX_ROUNDS}题。你一共答对了{state.score}题，太厉害了！"
                state.status = GameStatus.CHOOSING_GAME
                state.round_index = 0
                return GameHandleResult(
                    handled=True,
                    reply_text=reply,
                    state=state,
                    debug={
                        "engine": "riddle",
                        "action": "game_finished",
                        "final_score": state.score,
                    },
                )
            else:
                # Next riddle
                next_prompt = self._load_next_riddle(state)
                reply += f"我们来玩下一题吧。{next_prompt}"
                return GameHandleResult(
                    handled=True,
                    reply_text=reply,
                    state=state,
                    debug={
                        "engine": "riddle",
                        "action": "next_riddle",
                        "round": state.round_index,
                        "score": state.score,
                    },
                )

        else:
            state.attempts += 1

            if state.attempts == 1:
                # First wrong answer: give hint
                reply = f"不对呢。我给你一个提示：{state.hint}"
                return GameHandleResult(
                    handled=True,
                    reply_text=reply,
                    state=state,
                    debug={
                        "engine": "riddle",
                        "action": "hint",
                        "round": state.round_index,
                        "attempt": state.attempts,
                    },
                )

            elif state.attempts == 2:
                # Second wrong answer: reveal answer and next riddle
                reply = f"没有答对呢。正确答案是{state.expected_answer}。\n"

                if state.round_index >= self.MAX_ROUNDS - 1:
                    # Game finished
                    reply += f"我们已经完成了{self.MAX_ROUNDS}题。你一共答对了{state.score}题。"
                    state.status = GameStatus.CHOOSING_GAME
                    state.round_index = 0
                    return GameHandleResult(
                        handled=True,
                        reply_text=reply,
                        state=state,
                        debug={
                            "engine": "riddle",
                            "action": "game_finished",
                            "final_score": state.score,
                        },
                    )
                else:
                    # Next riddle
                    state.attempts = 0
                    next_prompt = self._load_next_riddle(state)
                    reply += f"我们来玩下一题吧。{next_prompt}"
                    return GameHandleResult(
                        handled=True,
                        reply_text=reply,
                        state=state,
                        debug={
                            "engine": "riddle",
                            "action": "next_riddle",
                            "round": state.round_index,
                            "score": state.score,
                        },
                    )

        # Should not reach here, but fallback
        return GameHandleResult(
            handled=False,
            debug={
                "engine": "riddle",
                "action": "unknown_state",
            },
        )

    def _load_next_riddle(self, state: GameState) -> str:
        """Load next riddle and return prompt."""
        state.round_index += 1
        riddle_indices = get_random_riddle_indices()

        if state.round_index - 1 >= len(riddle_indices):
            # Fallback
            riddle_idx = len(riddle_indices) - 1
        else:
            riddle_idx = riddle_indices[state.round_index - 1]

        riddle = RIDDLES[riddle_idx]
        state.current_prompt = riddle.question
        state.expected_answer = riddle.answer
        state.answer_aliases = riddle.aliases
        state.hint = riddle.hint
        state.attempts = 0

        return f"第{state.round_index}题：{riddle.question}"


# Global singleton instance
riddle_engine = RiddleEngine()
