from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from config import settings

from .schemas import MemoryEvent, safe_identifier


def _model_dump(model) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


class MemoryStore:
    """Append-only JSONL memory event store."""

    def __init__(self, data_dir: str | Path | None = None) -> None:
        self.root = Path(data_dir or settings.profile_data_dir)
        self.memories_dir = self.root / "memories"

    def ensure_dirs(self) -> None:
        self.memories_dir.mkdir(parents=True, exist_ok=True)

    def append_event(self, event: MemoryEvent) -> None:
        self.ensure_dirs()
        path = self.memory_path(event.user_id)
        with path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(_model_dump(event), ensure_ascii=False, default=str) + "\n")

    def read_events(self, user_id: str, *, include_summarized: bool = True) -> list[MemoryEvent]:
        path = self.memory_path(user_id)
        if not path.exists():
            return []
        events: list[MemoryEvent] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            text = line.strip()
            if not text:
                continue
            try:
                event = MemoryEvent(**json.loads(text))
            except Exception:
                continue
            if include_summarized or not event.summarized:
                events.append(event)
        return events

    def unsummarized_events(self, user_id: str) -> list[MemoryEvent]:
        return self.read_events(user_id, include_summarized=False)

    def count_unsummarized(self, user_id: str) -> int:
        return len(self.unsummarized_events(user_id))

    def mark_summarized(self, user_id: str, memory_ids: set[str]) -> None:
        if not memory_ids:
            return
        events = self.read_events(user_id, include_summarized=True)
        for event in events:
            if event.memory_id in memory_ids:
                event.summarized = True
        self._rewrite_events(user_id, events)

    def memory_path(self, user_id: str) -> Path:
        return self.memories_dir / f"{safe_identifier(user_id, fallback='anonymous')}.jsonl"

    def _rewrite_events(self, user_id: str, events: list[MemoryEvent]) -> None:
        self.ensure_dirs()
        path = self.memory_path(user_id)
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        with tmp_path.open("w", encoding="utf-8") as file:
            for event in events:
                file.write(json.dumps(_model_dump(event), ensure_ascii=False, default=str) + "\n")
        tmp_path.replace(path)


memory_store = MemoryStore()
