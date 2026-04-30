from __future__ import annotations

from dataclasses import dataclass

from shared.logging_utils import log_event


@dataclass
class SessionManager:
    session_id: str
    mode_id: str = "care"
    _turn_counter: int = 0

    def next_turn_id(self) -> str:
        self._turn_counter += 1
        turn_id = f"turn-{self._turn_counter:04d}"
        log_event("session_turn_created", session_id=self.session_id, turn_id=turn_id, mode_id=self.mode_id)
        return turn_id

    def apply_mode(self, mode_id: str | None) -> None:
        if mode_id:
            old_mode = self.mode_id
            self.mode_id = mode_id
            log_event("session_mode_applied", session_id=self.session_id, old_mode=old_mode, new_mode=self.mode_id)
