from dataclasses import dataclass, field
from typing import Protocol


class AudioPlayer(Protocol):
    def play_url(self, audio_url: str | None) -> None:
        ...

    def play_hint(self, text: str) -> None:
        ...


@dataclass
class MockAudioPlayer:
    played_urls: list[str | None] = field(default_factory=list)
    hints: list[str] = field(default_factory=list)

    def play_url(self, audio_url: str | None) -> None:
        self.played_urls.append(audio_url)

    def play_hint(self, text: str) -> None:
        self.hints.append(text)

