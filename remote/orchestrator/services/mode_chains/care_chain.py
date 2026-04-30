from __future__ import annotations

from typing import TYPE_CHECKING, Any

from logging_utils import log_event

from .base import BaseModeChain, ModeChainResult, ModeTurnContext

if TYPE_CHECKING:
    from clients.llm_client import LLMClient
    from services.response_policy_service import ResponsePolicyService


class CareModeChain(BaseModeChain):
    """Care mode chain: elderly companion, emotional comfort, safety-first."""

    mode_id = "care"

    def handle_turn(
        self,
        context: ModeTurnContext,
        llm_client: Any,
        response_policy_service: Any,
    ) -> ModeChainResult:
        """Handle care mode turn: LLM + response policy."""
        debug_info: dict[str, Any] = {
            "chain": "care",
            "session_id": context.session_id,
            "turn_id": context.turn_id,
        }

        try:
            # 1. Generate LLM reply using care policy and RAG
            llm_result = llm_client.generate_reply(
                session_id=context.session_id,
                turn_id=context.turn_id,
                asr_text=context.asr_text,
                mode_policy=context.mode_policy,
                rag_route=context.rag_route,
                rag_context=context.rag_context,
            )
            debug_info["llm_source"] = llm_result.source

            # 2. Apply care-specific response policy
            response_result = response_policy_service.apply(
                mode_id="care",
                reply_text=llm_result.reply_text,
                user_text=context.asr_text,
            )
            debug_info["response_policy_changed"] = response_result.changed
            debug_info["response_policy_rules"] = response_result.rules_applied
            debug_info["response_policy_original_chars"] = response_result.original_chars
            debug_info["response_policy_final_chars"] = response_result.final_chars

            # 3. Return handled result
            result = ModeChainResult(
                handled=True,
                reply_text=response_result.reply_text,
                llm_result=llm_result,
                rag_context=context.rag_context,
                debug=debug_info,
            )

            log_event(
                "care_mode_chain_handled",
                session_id=context.session_id,
                turn_id=context.turn_id,
                reply_text_len=len(response_result.reply_text),
                response_policy_changed=response_result.changed,
            )

            return result
        except Exception as exc:
            debug_info["error"] = str(exc)
            debug_info["error_type"] = type(exc).__name__
            log_event(
                "care_mode_chain_error",
                session_id=context.session_id,
                turn_id=context.turn_id,
                error=str(exc),
            )
            return ModeChainResult(
                handled=False,
                debug=debug_info,
            )

