from __future__ import annotations

from typing import Any

from .base import BaseModeChain, ModeChainResult, ModeTurnContext


class GameModeChain(BaseModeChain):
    """Game mode chain: reserved for future GameStateService."""

    mode_id = "game"

    def handle_turn(
        self,
        context: ModeTurnContext,
        llm_client: Any,
        response_policy_service: Any,
    ) -> ModeChainResult:
        """Game mode not yet optimized; fallback to generic LLM flow."""
        return ModeChainResult(
            handled=False,
            debug={
                "chain": "game",
                "reason": "game_chain_reserved_for_future",
                "fallback": "generic_llm_flow",
                "note": "GameStateService planned for later phases",
            },
        )

