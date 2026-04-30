from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ModeTurnContext:
    session_id: str
    turn_id: str
    mode_id: str
    asr_text: str
    rag_context: str | None = None
    emotion_label: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ModeChainResult:
    handled: bool = False
    reply_text: str | None = None
    rag_context: str | None = None
    robot_action_hint: dict[str, Any] | None = None
    debug: dict[str, Any] = field(default_factory=dict)


class BaseModeChain:
    mode_id: str = ""

    def handle_turn(self, context: ModeTurnContext) -> ModeChainResult:
        return ModeChainResult(
            handled=False,
            debug={
                "mode_id": self.mode_id,
                "todo": "ModeChain is reserved and not wired into RobotChatService yet.",
                "input_mode_id": context.mode_id,
            },
        )
