from __future__ import annotations

from .base import BaseModeChain, ModeChainResult, ModeTurnContext


class LearningModeChain(BaseModeChain):
    mode_id = "learning"

    def handle_turn(self, context: ModeTurnContext) -> ModeChainResult:
        # TODO:
        # - learning intent classification
        # - plan/explain/quiz/encourage
        # - optional learning RAG later
        return super().handle_turn(context)
