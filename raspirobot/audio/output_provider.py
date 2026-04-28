from __future__ import annotations

import shlex
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol
from urllib.parse import urljoin, urlparse
from urllib.request import urlopen

from raspirobot.utils import ensure_dir, safe_child_name
from shared.logging_utils import log_event


@dataclass(frozen=True)
class PlaybackResult:
    played: bool
    source: str | None
    local_path: Path | None = None
    skipped_reason: str | None = None


class AudioOutputProvider(Protocol):
    def play_audio_url(self, audio_url: str | None, *, base_url: str | None = None) -> PlaybackResult:
        ...

    def play_wav_file(self, path: str | Path) -> PlaybackResult:
        ...


@dataclass
class MockAudioOutputProvider:
    played_urls: list[str | None] = field(default_factory=list)
    played_files: list[str] = field(default_factory=list)

    def play_audio_url(self, audio_url: str | None, *, base_url: str | None = None) -> PlaybackResult:
        self.played_urls.append(audio_url)
        if not audio_url or audio_url.startswith("mock://"):
            result = PlaybackResult(
                played=False,
                source=audio_url,
                skipped_reason="empty audio_url" if not audio_url else "mock audio_url is not playable",
            )
            log_event("playback_skipped", source=audio_url, skipped_reason=result.skipped_reason)
            return result
        log_event("playback_started", source=audio_url, provider="mock")
        result = PlaybackResult(played=True, source=audio_url)
        log_event("playback_done", source=audio_url, provider="mock")
        return result

    def play_wav_file(self, path: str | Path) -> PlaybackResult:
        path_text = str(path)
        self.played_files.append(path_text)
        log_event("playback_started", source=path_text, local_path=path_text, provider="mock")
        result = PlaybackResult(played=True, source=path_text, local_path=Path(path))
        log_event("playback_done", source=path_text, local_path=path_text, provider="mock")
        return result


@dataclass
class LocalCommandAudioOutputProvider:
    command: str = "aplay"
    playback_device: str | None = None
    download_dir: str | Path = "/tmp/raspirobot_audio/playback"

    def play_audio_url(self, audio_url: str | None, *, base_url: str | None = None) -> PlaybackResult:
        if not audio_url:
            result = PlaybackResult(played=False, source=audio_url, skipped_reason="empty audio_url")
            log_event("playback_skipped", source=audio_url, skipped_reason=result.skipped_reason)
            return result
        if audio_url.startswith("mock://"):
            result = PlaybackResult(played=False, source=audio_url, skipped_reason="mock audio_url is not playable")
            log_event("playback_skipped", source=audio_url, skipped_reason=result.skipped_reason)
            return result

        try:
            local_path = self._resolve_to_local_file(audio_url, base_url=base_url)
        except Exception as exc:
            result = PlaybackResult(played=False, source=audio_url, skipped_reason=f"download_failed:{exc}")
            log_event("playback_skipped", source=audio_url, skipped_reason=result.skipped_reason, level="error")
            return result
        return self.play_wav_file(local_path)

    def play_wav_file(self, path: str | Path) -> PlaybackResult:
        wav_path = Path(path)
        if not wav_path.exists():
            result = PlaybackResult(played=False, source=str(path), skipped_reason="file does not exist")
            log_event("playback_skipped", source=str(path), skipped_reason=result.skipped_reason)
            return result

        cmd = shlex.split(self.command)
        if not cmd:
            cmd = ["aplay"]

        if Path(cmd[0]).name == "aplay" and self.playback_device:
            cmd.extend(["-D", self.playback_device])
        cmd.append(str(wav_path))

        log_event(
            "playback_started",
            source=str(path),
            local_path=str(wav_path),
            command=" ".join(cmd),
            playback_device=self.playback_device,
        )
        completed = subprocess.run(cmd, check=False, capture_output=True, text=True)
        if completed.returncode != 0:
            reason = (completed.stderr or completed.stdout or "playback command failed").strip()
            result = PlaybackResult(played=False, source=str(path), local_path=wav_path, skipped_reason=reason)
            log_event("playback_skipped", source=str(path), local_path=str(wav_path), skipped_reason=reason, level="error")
            return result
        result = PlaybackResult(played=True, source=str(path), local_path=wav_path)
        log_event("playback_done", source=str(path), local_path=str(wav_path))
        return result

    def _resolve_to_local_file(self, audio_url: str, *, base_url: str | None = None) -> Path:
        parsed = urlparse(audio_url)
        if parsed.scheme == "file":
            return Path(parsed.path)
        if parsed.scheme == "":
            if audio_url.startswith("/"):
                if not base_url:
                    raise ValueError("Relative audio_url requires base_url.")
                download_url = urljoin(f"{base_url.rstrip('/')}/", audio_url.lstrip("/"))
            else:
                return Path(audio_url)
        elif parsed.scheme in {"http", "https"}:
            download_url = audio_url
        else:
            raise ValueError(f"Unsupported audio_url scheme: {parsed.scheme}")

        download_dir = ensure_dir(self.download_dir)
        name = safe_child_name(Path(urlparse(download_url).path).name or "tts.wav")
        local_path = download_dir / name
        with urlopen(download_url, timeout=30) as response:
            local_path.write_bytes(response.read())
        return local_path
