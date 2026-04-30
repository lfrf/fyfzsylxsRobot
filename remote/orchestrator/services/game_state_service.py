from __future__ import annotations

# Re-export from games package for backward compatibility
from games.game_state_service import GameStateService, game_state_service

__all__ = ["GameStateService", "game_state_service"]
