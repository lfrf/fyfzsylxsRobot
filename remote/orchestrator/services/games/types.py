from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime


class GameStatus(str, Enum):
    """Game state status."""
    IDLE = "IDLE"
    CHOOSING_GAME = "CHOOSING_GAME"
    RIDDLE_WAITING_ANSWER = "RIDDLE_WAITING_ANSWER"
    WORD_CHAIN_WAITING_ANSWER = "WORD_CHAIN_WAITING_ANSWER"


class GameType(str, Enum):
    """Game type."""
    RIDDLE = "RIDDLE"
    WORD_CHAIN = "WORD_CHAIN"


class GameIntent(str, Enum):
    """User intent in game context."""
    NONE = "NONE"
    START_GAME = "START_GAME"
    EXIT_GAME = "EXIT_GAME"
    SELECT_RIDDLE = "SELECT_RIDDLE"
    SELECT_WORD_CHAIN = "SELECT_WORD_CHAIN"
    HELP = "HELP"


@dataclass
class GameState:
    """Game state for a session."""
    session_id: str
    status: GameStatus = GameStatus.IDLE
    game_type: GameType | None = None
    round_index: int = 0
    score: int = 0
    current_prompt: str | None = None
    expected_answer: str | None = None
    answer_aliases: list[str] = field(default_factory=list)
    hint: str | None = None
    attempts: int = 0
    current_word: str | None = None
    history: list[str] = field(default_factory=list)
    unknown_count: int = 0
    updated_at: datetime = field(default_factory=datetime.now)

    def reset(self):
        """Reset game state."""
        self.status = GameStatus.IDLE
        self.game_type = None
        self.round_index = 0
        self.score = 0
        self.current_prompt = None
        self.expected_answer = None
        self.answer_aliases = []
        self.hint = None
        self.attempts = 0
        self.current_word = None
        self.history = []
        self.unknown_count = 0
        self.updated_at = datetime.now()


@dataclass
class GameHandleResult:
    """Result of handling a game turn."""
    handled: bool = False
    reply_text: str | None = None
    state: GameState | None = None
    mode_update: str | None = None
    robot_action_hint: dict | None = None
    debug: dict = field(default_factory=dict)
