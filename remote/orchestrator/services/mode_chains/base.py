from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from services.mode_types import ModePolicy
    from services.rag_router import RagRoute


@dataclass(frozen=True)
class ModeTurnContext:
    """Context for a mode chain turn."""

    session_id: str
    turn_id: str
    mode_id: str
    asr_text: str
    mode_policy: Any | None = None  # ModePolicy, avoid circular import
    rag_route: Any | None = None  # RagRoute, avoid circular import
    rag_context: str | None = None
    emotion_label: str | None = None
    vision_context: Any | None = None
    robot_state: Any | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ModeChainResult:
    """Result of mode chain processing."""

    handled: bool = False
    reply_text: str | None = None
    llm_result: Any | None = None  # LLMResult, avoid circular import
    rag_context: str | None = None
    robot_action_hint: dict[str, Any] | None = None
    debug: dict[str, Any] = field(default_factory=dict)


class BaseModeChain:
    """Base class for mode-specific processing chains."""

    mode_id: str = ""

    def handle_turn(
        self,
        context: ModeTurnContext,
        llm_client: Any,
        response_policy_service: Any,
    ) -> ModeChainResult:
        """Process a turn in the mode chain.

        Args:
            context: ModeTurnContext with session, turn, mode, text, etc.
            llm_client: LLMClient instance
            response_policy_service: ResponsePolicyService instance

        Returns:
            ModeChainResult with handled flag and reply_text if handled=True.
        """
        return ModeChainResult(
            handled=False,
            debug={
                "mode_id": self.mode_id,
                "reason": "skeleton_not_implemented",
                "input_mode_id": context.mode_id,
            },
        )
