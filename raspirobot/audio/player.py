from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from .output_provider import AudioOutputProvider, LocalCommandAudioOutputProvider, MockAudioOutputProvider, PlaybackResult


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

    def play_audio_url(self, audio_url: str | None, *, base_url: str | None = None) -> PlaybackResult:
        self.play_url(audio_url)
        return PlaybackResult(played=bool(audio_url), source=audio_url)

    def play_wav_file(self, path: str | Path) -> PlaybackResult:
        self.play_url(str(path))
        return PlaybackResult(played=True, source=str(path), local_path=Path(path))


__all__ = [
    "AudioOutputProvider",
    "AudioPlayer",
    "LocalCommandAudioOutputProvider",
    "MockAudioOutputProvider",
    "MockAudioPlayer",
    "PlaybackResult",
]
