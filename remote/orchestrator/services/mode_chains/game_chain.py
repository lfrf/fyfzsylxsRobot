from __future__ import annotations

from typing import TYPE_CHECKING, Any

from logging_utils import log_event
from services.games.game_state_service import game_state_service

from .base import BaseModeChain, ModeChainResult, ModeTurnContext

if TYPE_CHECKING:
    from clients.llm_client import LLMClient
    from services.response_policy_service import ResponsePolicyService


class GameModeChain(BaseModeChain):
    """Game mode chain: riddles and word chain games."""

    mode_id = "game"

    def handle_turn(
        self,
        context: ModeTurnContext,
        llm_client: Any,
        response_policy_service: Any,
    ) -> ModeChainResult:
        """Handle game mode turn using GameStateService."""
        debug_info: dict[str, Any] = {
            "chain": "game",
            "session_id": context.session_id,
            "turn_id": context.turn_id,
            "mode_update": None,
        }

        try:
            state_before = game_state_service.get_or_create_state(context.session_id)
            debug_info.update(self._state_debug(state_before))

            # Use GameStateService to handle game logic
            game_result = game_state_service.handle_turn(
                session_id=context.session_id,
                asr_text=context.asr_text,
            )

            if not game_result.handled:
                debug_info["reason"] = "game_not_active"
                debug_info.update(self._state_debug(game_result.state or state_before))
                return ModeChainResult(
                    handled=False,
                    debug=debug_info,
                )

            # Game is handled
            reply_text = game_result.reply_text or ""
            mode_update = game_result.mode_update

            debug_info["handled"] = True
            debug_info.update(game_result.debug)
            debug_info.update(self._state_debug(game_result.state))

            # Set robot action hint for game
            robot_action_hint = game_result.robot_action_hint or {
                "expression": "happy",
                "motion": "happy_nod",
                "speech_style": "game_playful",
            }

            if mode_update:
                debug_info["mode_update"] = mode_update

            log_event(
                "game_mode_chain_handled",
                session_id=context.session_id,
                turn_id=context.turn_id,
                reply_text_len=len(reply_text),
                mode_update=mode_update,
            )

            return ModeChainResult(
                handled=True,
                reply_text=reply_text,
                robot_action_hint=robot_action_hint,
                debug=debug_info,
            )

        except Exception as exc:
            debug_info["error"] = str(exc)
            debug_info["error_type"] = type(exc).__name__
            log_event(
                "game_mode_chain_error",
                session_id=context.session_id,
                turn_id=context.turn_id,
                error=str(exc),
            )
            # Fallback on error
            return ModeChainResult(
                handled=False,
                debug=debug_info,
            )

    def _state_debug(self, state: Any | None) -> dict[str, Any]:
        if state is None:
            return {
                "game_status": None,
                "game_type": None,
                "round_index": 0,
                "score": 0,
            }
        game_status = getattr(state, "status", None)
        game_type = getattr(state, "game_type", None)
        return {
            "game_status": getattr(game_status, "value", game_status),
            "game_type": getattr(game_type, "value", game_type),
            "round_index": getattr(state, "round_index", 0),
            "score": getattr(state, "score", 0),
        }
