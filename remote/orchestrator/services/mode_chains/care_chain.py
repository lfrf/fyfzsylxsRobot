from __future__ import annotations

from .base import BaseModeChain, ModeChainResult, ModeTurnContext


class CareModeChain(BaseModeChain):
    mode_id = "care"

    def handle_turn(self, context: ModeTurnContext) -> ModeChainResult:
        # TODO:
        # - risk classification
        # - care RAG
        # - safety boundary
        # - response policy
        return super().handle_turn(context)
