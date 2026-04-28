from __future__ import annotations

from collections import defaultdict
from typing import Callable

from .events import RuntimeEvent, RuntimeEventType


EventHandler = Callable[[RuntimeEvent], None]


class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[RuntimeEventType, list[EventHandler]] = defaultdict(list)
        self.events: list[RuntimeEvent] = []

    def subscribe(self, event_type: RuntimeEventType, handler: EventHandler) -> None:
        self._handlers[event_type].append(handler)

    def publish(self, event: RuntimeEvent) -> None:
        self.events.append(event)
        for handler in self._handlers.get(event.type, []):
            handler(event)
