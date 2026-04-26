from collections import defaultdict
from dataclasses import dataclass

from config import settings
from models import ContextMessage


@dataclass
class ConversationRecord:
    role: str
    content: str
    turn_id: int
    input_mode: str


class SessionState:
    def __init__(self) -> None:
        self._history: dict[str, list[ConversationRecord]] = defaultdict(list)

    def append_message(
        self,
        session_id: str,
        *,
        role: str,
        content: str,
        turn_id: int,
        input_mode: str,
    ) -> None:
        if not content:
            return

        self._history[session_id].append(
            ConversationRecord(
                role=role,
                content=content,
                turn_id=turn_id,
                input_mode=input_mode,
            )
        )

    def build_context_messages(self, session_id: str) -> list[ContextMessage]:
        messages = self._history.get(session_id, [])
        if not messages:
            return []

        selected = messages[-settings.max_context_messages :]
        return [
            ContextMessage(
                role=item.role,
                content=item.content,
                turn_id=item.turn_id,
                input_mode=item.input_mode,
            )
            for item in selected
        ]

    def get_summary(self, session_id: str) -> str:
        messages = self._history.get(session_id, [])
        if not messages:
            return ""

        selected = messages[-settings.context_summary_turns :]
        summary_parts = [f"{item.role}:{item.content}" for item in selected]
        return " | ".join(summary_parts)


session_state = SessionState()
