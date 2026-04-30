from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SessionManager:
    session_id: str
    mode_id: str = "care"
    _turn_counter: int = 0

    def next_turn_id(self) -> str:
        self._turn_counter += 1
        return f"turn-{self._turn_counter:04d}"

    def apply_mode(self, mode_id: str | None) -> None:
        if mode_id:
            self.mode_id = mode_id
