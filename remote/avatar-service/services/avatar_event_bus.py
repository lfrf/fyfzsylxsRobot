import asyncio
from dataclasses import dataclass
from typing import Any

from fastapi import WebSocket


@dataclass
class _AvatarSubscriber:
    websocket: WebSocket
    session_id: str | None = None
    stream_id: str | None = None


class AvatarEventBus:
    def __init__(self) -> None:
        self._subscribers: dict[int, _AvatarSubscriber] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._subscribers[id(websocket)] = _AvatarSubscriber(websocket=websocket)

    async def set_subscription(
        self,
        websocket: WebSocket,
        *,
        session_id: str | None = None,
        stream_id: str | None = None,
    ) -> None:
        async with self._lock:
            subscriber = self._subscribers.get(id(websocket))
            if not subscriber:
                return
            subscriber.session_id = (session_id or "").strip() or None
            subscriber.stream_id = (stream_id or "").strip() or None

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._subscribers.pop(id(websocket), None)

    async def publish(
        self,
        *,
        payload: dict[str, Any],
        session_id: str | None = None,
        stream_id: str | None = None,
    ) -> int:
        async with self._lock:
            subscribers = list(self._subscribers.items())

        delivered = 0
        stale_ids: list[int] = []
        for subscriber_id, subscriber in subscribers:
            if not self._matches(subscriber, session_id=session_id, stream_id=stream_id):
                continue
            try:
                await subscriber.websocket.send_json(payload)
                delivered += 1
            except Exception:
                stale_ids.append(subscriber_id)

        if stale_ids:
            async with self._lock:
                for stale_id in stale_ids:
                    self._subscribers.pop(stale_id, None)
        return delivered

    def _matches(self, subscriber: _AvatarSubscriber, *, session_id: str | None, stream_id: str | None) -> bool:
        if subscriber.session_id and session_id and subscriber.session_id != session_id:
            return False
        if subscriber.stream_id and stream_id and subscriber.stream_id != stream_id:
            return False
        return True


avatar_event_bus = AvatarEventBus()
