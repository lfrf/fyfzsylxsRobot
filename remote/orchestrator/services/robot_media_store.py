from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RobotMediaStore:
    _tts_urls: dict[tuple[str, str], str] = field(default_factory=dict)

    def register(self, *, session_id: str, turn_id: str, upstream_url: str) -> None:
        self._tts_urls[(session_id, turn_id)] = upstream_url

    def get_tts_url(self, *, session_id: str, turn_id: str) -> str | None:
        return self._tts_urls.get((session_id, turn_id))


robot_media_store = RobotMediaStore()

__all__ = ["RobotMediaStore", "robot_media_store"]
