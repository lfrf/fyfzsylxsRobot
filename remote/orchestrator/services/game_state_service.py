from __future__ import annotations


class GameStateService:
    """Reserved interface for future voice-game state machines."""

    def detect_game_intent(self, text: str | None) -> bool:
        return False

    def handle_game_turn(self, *, session_id: str, text: str) -> str | None:
        return None

    def reset_game(self, session_id: str) -> None:
        return None


game_state_service = GameStateService()

__all__ = ["GameStateService", "game_state_service"]
