import threading
import time
from dataclasses import dataclass


@dataclass
class BufferedAudioChunk:
    sequence_id: int
    audio_bytes: bytes
    audio_format: str
    audio_duration_ms: int | None = None
    audio_sample_rate_hz: int | None = None
    audio_channels: int | None = None


class AudioStreamBuffer:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._storage: dict[str, list[BufferedAudioChunk]] = {}
        self._updated_at_ms: dict[str, int] = {}
        self._ttl_ms = 10 * 60 * 1000

    def append(
        self,
        *,
        key: str,
        chunks: list[BufferedAudioChunk],
    ) -> int:
        now_ms = int(time.time() * 1000)
        with self._lock:
            self._evict_expired_locked(now_ms)
            queue = self._storage.setdefault(key, [])
            queue.extend(chunks)
            queue.sort(key=lambda chunk: chunk.sequence_id)
            self._updated_at_ms[key] = now_ms
            return len(queue)

    def snapshot(self, *, key: str) -> list[BufferedAudioChunk]:
        with self._lock:
            queue = self._storage.get(key, [])
            return list(queue)

    def pop(self, *, key: str) -> list[BufferedAudioChunk]:
        with self._lock:
            queue = self._storage.pop(key, [])
            self._updated_at_ms.pop(key, None)
            return list(queue)

    def clear(self, *, key: str) -> None:
        with self._lock:
            self._storage.pop(key, None)
            self._updated_at_ms.pop(key, None)

    def _evict_expired_locked(self, now_ms: int) -> None:
        expired_keys = [
            key for key, updated_at_ms in self._updated_at_ms.items() if now_ms - updated_at_ms > self._ttl_ms
        ]
        for key in expired_keys:
            self._storage.pop(key, None)
            self._updated_at_ms.pop(key, None)


audio_stream_buffer = AudioStreamBuffer()
