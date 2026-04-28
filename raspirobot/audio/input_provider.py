from __future__ import annotations

import math
import shlex
import subprocess
import wave
from dataclasses import dataclass
from pathlib import Path
from time import time
from typing import Iterable, Iterator, Protocol


@dataclass(frozen=True)
class AudioFrame:
    pcm: bytes
    sample_rate: int
    channels: int
    sample_width: int = 2
    timestamp: float | None = None

    @property
    def duration_ms(self) -> int:
        if self.sample_rate <= 0 or self.channels <= 0 or self.sample_width <= 0:
            return 0
        sample_count = len(self.pcm) // (self.channels * self.sample_width)
        return int(sample_count * 1000 / self.sample_rate)


class AudioInputProvider(Protocol):
    sample_rate: int
    channels: int
    sample_width: int
    frame_ms: int

    def frames(self) -> Iterator[AudioFrame]:
        ...


@dataclass
class MockAudioInputProvider:
    frame_plan: Iterable[bytes]
    sample_rate: int = 16000
    channels: int = 1
    sample_width: int = 2
    frame_ms: int = 30

    def frames(self) -> Iterator[AudioFrame]:
        for pcm in self.frame_plan:
            yield AudioFrame(
                pcm=pcm,
                sample_rate=self.sample_rate,
                channels=self.channels,
                sample_width=self.sample_width,
                timestamp=time(),
            )


@dataclass
class FileAudioInputProvider:
    wav_path: str | Path
    frame_ms: int = 30
    realtime: bool = False

    def __post_init__(self) -> None:
        with wave.open(str(self.wav_path), "rb") as wav:
            self.sample_rate = wav.getframerate()
            self.channels = wav.getnchannels()
            self.sample_width = wav.getsampwidth()

    def frames(self) -> Iterator[AudioFrame]:
        with wave.open(str(self.wav_path), "rb") as wav:
            frames_per_chunk = max(1, int(wav.getframerate() * self.frame_ms / 1000))
            while True:
                pcm = wav.readframes(frames_per_chunk)
                if not pcm:
                    break
                yield AudioFrame(
                    pcm=pcm,
                    sample_rate=wav.getframerate(),
                    channels=wav.getnchannels(),
                    sample_width=wav.getsampwidth(),
                    timestamp=time(),
                )


@dataclass
class LocalCommandAudioInputProvider:
    sample_rate: int = 16000
    channels: int = 1
    sample_width: int = 2
    frame_ms: int = 30
    capture_device: str | None = None
    command: str = "arecord"

    def frames(self) -> Iterator[AudioFrame]:
        if self.sample_width != 2:
            raise ValueError("LocalCommandAudioInputProvider currently supports 16-bit PCM only.")

        cmd = shlex.split(self.command)
        if not cmd:
            cmd = ["arecord"]
        if self.capture_device:
            cmd.extend(["-D", self.capture_device])
        cmd.extend(
            [
                "-q",
                "-f",
                "S16_LE",
                "-r",
                str(self.sample_rate),
                "-c",
                str(self.channels),
                "-t",
                "raw",
            ]
        )

        bytes_per_frame = int(self.sample_rate * self.channels * self.sample_width * self.frame_ms / 1000)
        bytes_per_frame = max(self.channels * self.sample_width, bytes_per_frame)

        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        assert process.stdout is not None
        try:
            while True:
                pcm = process.stdout.read(bytes_per_frame)
                if not pcm:
                    break
                yield AudioFrame(
                    pcm=pcm,
                    sample_rate=self.sample_rate,
                    channels=self.channels,
                    sample_width=self.sample_width,
                    timestamp=time(),
                )
                if len(pcm) < bytes_per_frame:
                    break
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()


def make_sine_pcm(
    *,
    duration_ms: int,
    sample_rate: int = 16000,
    channels: int = 1,
    frequency_hz: float = 440.0,
    amplitude: int = 6000,
) -> bytes:
    sample_count = int(sample_rate * duration_ms / 1000)
    chunks: list[int] = []
    for index in range(sample_count):
        value = int(amplitude * math.sin(2 * math.pi * frequency_hz * index / sample_rate))
        chunks.extend([value] * channels)
    return b"".join(int(sample).to_bytes(2, "little", signed=True) for sample in chunks)


def make_silence_pcm(*, duration_ms: int, sample_rate: int = 16000, channels: int = 1) -> bytes:
    sample_count = int(sample_rate * duration_ms / 1000)
    return b"\x00\x00" * sample_count * channels
