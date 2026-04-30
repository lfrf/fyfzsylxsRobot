from __future__ import annotations

from .types import GameHandleResult, GameState, GameStatus, GameType
from .assets import (
    get_word_chain_starting_word,
    find_next_word,
    extract_word_from_user_input,
    normalize_text,
)


class WordChainEngine:
    """Engine for handling word chain game logic."""

    MAX_ROUNDS = 8

    def start(self, state: GameState) -> GameHandleResult:
        """Start word chain game."""
        state.game_type = GameType.WORD_CHAIN
        state.round_index = 0
        state.score = 0
        state.current_word = get_word_chain_starting_word()
        state.history = [state.current_word]
        state.status = GameStatus.WORD_CHAIN_WAITING_ANSWER

        reply = f"好，我们来玩词语接龙。我先来：{state.current_word}。你接一个以'{state.current_word[-1]}'开头的词吧。"

        return GameHandleResult(
            handled=True,
            reply_text=reply,
            state=state,
            debug={
                "engine": "word_chain",
                "action": "start",
                "starting_word": state.current_word,
            },
        )

    def handle_answer(self, state: GameState, user_text: str) -> GameHandleResult:
        """Handle user answer in word chain game."""
        # Extract word from user input
        user_word = extract_word_from_user_input(user_text)

        if not user_word:
            return GameHandleResult(
                handled=True,
                reply_text="我没听清你说的词语。请再说一遍，或者给我一个清楚的词语。",
                state=state,
                debug={
                    "engine": "word_chain",
                    "action": "unclear_input",
                    "raw_input": user_text,
                },
            )

        # Check if first character matches last character of current word
        if state.current_word and user_word and user_word[0] != state.current_word[-1]:
            return GameHandleResult(
                handled=True,
                reply_text=f"不对哦，应该接以'{state.current_word[-1]}'开头的词。你再想想吧。",
                state=state,
                debug={
                    "engine": "word_chain",
                    "action": "wrong_connection",
                    "expected_start": state.current_word[-1],
                    "user_word": user_word,
                },
            )

        # Check if word already used
        if user_word in state.history:
            return GameHandleResult(
                handled=True,
                reply_text=f"'{user_word}'我们已经玩过了。换一个词吧。",
                state=state,
                debug={
                    "engine": "word_chain",
                    "action": "word_repeated",
                    "user_word": user_word,
                },
            )

        # Correct answer
        state.history.append(user_word)
        state.score += 1
        state.round_index += 1

        # Find next word from engine
        exclude_words = set(state.history)
        next_word = find_next_word(user_word[-1], exclude_words)

        if not next_word:
            # Engine cannot continue - user wins
            reply = f"哇，你赢了！我找不到能接'{user_word[-1]}'的词了。你真厉害！"
            state.status = GameStatus.CHOOSING_GAME
            state.round_index = 0
            return GameHandleResult(
                handled=True,
                reply_text=reply,
                state=state,
                debug={
                    "engine": "word_chain",
                    "action": "user_wins",
                    "final_score": state.score,
                },
            )

        # Check if max rounds reached
        if state.round_index >= self.MAX_ROUNDS:
            reply = f"恭喜你！我们已经接了{state.round_index}个词了。你真厉害！"
            state.status = GameStatus.CHOOSING_GAME
            state.round_index = 0
            return GameHandleResult(
                handled=True,
                reply_text=reply,
                state=state,
                debug={
                    "engine": "word_chain",
                    "action": "max_rounds_reached",
                    "final_score": state.score,
                },
            )

        # Continue game
        state.current_word = next_word
        state.history.append(next_word)
        reply = f"好接！我说：{next_word}。现在该你了，接一个以'{next_word[-1]}'开头的词。"

        return GameHandleResult(
            handled=True,
            reply_text=reply,
            state=state,
            debug={
                "engine": "word_chain",
                "action": "continue",
                "user_word": user_word,
                "engine_word": next_word,
                "round": state.round_index,
                "score": state.score,
            },
        )


# Global singleton instance
word_chain_engine = WordChainEngine()
