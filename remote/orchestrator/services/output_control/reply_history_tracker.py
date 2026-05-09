from __future__ import annotations

from collections import defaultdict, deque

from config import settings
from logging_utils import log_event

from .schemas import ReplyHistoryItem


class ReplyHistoryTracker:
    DEFAULT_AVOID_PHRASES = (
        "我在这里陪你",
        "慢慢说",
        "喝点水",
        "休息一下",
        "别着急",
        "你愿意说说吗",
    )

    def __init__(self, history_size: int | None = None) -> None:
        self.history_size = history_size or settings.reply_history_size
        self._items: dict[str, deque[ReplyHistoryItem]] = defaultdict(lambda: deque(maxlen=self.history_size))

    def record(self, session_id: str, mode_id: str, strategy_id: str | None, reply_text: str) -> None:
        item = ReplyHistoryItem(mode_id=mode_id, strategy_id=strategy_id, reply_text=reply_text or "")
        history = self._items[session_id]
        history.append(item)
        log_event(
            "reply_history_recorded",
            session_id=session_id,
            mode_id=mode_id,
            strategy_id=strategy_id,
            history_size=len(history),
        )

    def get_recent(self, session_id: str, limit: int | None = None) -> list[ReplyHistoryItem]:
        items = list(self._items.get(session_id, deque()))
        if limit is not None:
            return items[-limit:]
        return items

    def get_recent_strategy_ids(self, session_id: str, limit: int | None = None) -> list[str]:
        return [item.strategy_id for item in self.get_recent(session_id, limit) if item.strategy_id]

    def get_recent_reply_texts(self, session_id: str, limit: int | None = None) -> list[str]:
        return [item.reply_text for item in self.get_recent(session_id, limit) if item.reply_text]

    def get_avoid_phrases(self, session_id: str) -> list[str]:
        recent_text = "\n".join(self.get_recent_reply_texts(session_id))
        avoid = []
        for phrase in self.DEFAULT_AVOID_PHRASES:
            if phrase in recent_text:
                avoid.append(phrase)
        return avoid


reply_history_tracker = ReplyHistoryTracker()
