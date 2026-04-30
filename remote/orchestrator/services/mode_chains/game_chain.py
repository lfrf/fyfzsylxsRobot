from __future__ import annotations

from .base import BaseModeChain, ModeChainResult, ModeTurnContext


class GameModeChain(BaseModeChain):
    mode_id = "game"

    def handle_turn(self, context: ModeTurnContext) -> ModeChainResult:
        # TODO:
        # - GameStateService later
        # - riddle/word chain/story chain
        return super().handle_turn(context)
