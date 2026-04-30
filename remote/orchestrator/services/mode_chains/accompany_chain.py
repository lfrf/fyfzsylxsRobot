from __future__ import annotations

from .base import BaseModeChain, ModeChainResult, ModeTurnContext


class AccompanyModeChain(BaseModeChain):
    mode_id = "accompany"

    def handle_turn(self, context: ModeTurnContext) -> ModeChainResult:
        # TODO:
        # - emotion/casual intent
        # - natural follow-up
        # - user memory later
        return super().handle_turn(context)
