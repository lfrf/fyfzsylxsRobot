from __future__ import annotations

import wave
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class WavInfo:
    path: Path
    sample_rate: int
    channels: int
    sample_width: int
    frame_count: int
    duration_ms: int


def read_wav_info(path: str | Path) -> WavInfo:
    wav_path = Path(path)
    with wave.open(str(wav_path), "rb") as wav:
        frame_count = wav.getnframes()
        sample_rate = wav.getframerate()
        duration_ms = int(frame_count * 1000 / sample_rate) if sample_rate else 0
        return WavInfo(
            path=wav_path,
            sample_rate=sample_rate,
            channels=wav.getnchannels(),
            sample_width=wav.getsampwidth(),
            frame_count=frame_count,
            duration_ms=duration_ms,
        )


def write_wav(
    path: str | Path,
    frames: list[bytes],
    *,
    sample_rate: int,
    channels: int,
    sample_width: int = 2,
) -> WavInfo:
    wav_path = Path(path)
    wav_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(wav_path), "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(sample_width)
        wav.setframerate(sample_rate)
        wav.writeframes(b"".join(frames))
    return read_wav_info(wav_path)
