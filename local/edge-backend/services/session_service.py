from collections import defaultdict
from uuid import uuid4

from config import settings


class SessionService:
    def __init__(self, session_prefix: str) -> None:
        self._session_prefix = session_prefix
        self._turn_counters: dict[str, int] = defaultdict(int)

    def ensure_session(self, session_id: str | None) -> str:
        if session_id:
            return session_id
        return f"{self._session_prefix}-{uuid4().hex[:8]}"

    def ensure_turn(self, session_id: str, turn_id: int | None) -> int:
        if turn_id is not None:
            self._turn_counters[session_id] = max(self._turn_counters[session_id], turn_id)
            return turn_id

        self._turn_counters[session_id] += 1
        return self._turn_counters[session_id]


session_service = SessionService(session_prefix=settings.default_session_prefix)
