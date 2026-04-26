import base64
import io
import wave
from dataclasses import dataclass


@dataclass
class DecodedAudio:
    sample_rate_hz: int
    channels: int
    frame_count: int
    sample_width_bytes: int
    samples_by_channel: list[list[float]]


def decode_audio_base64(audio_base64: str) -> bytes:
    try:
        return base64.b64decode(audio_base64)
    except Exception as exc:  # noqa: BLE001
        raise ValueError("Audio payload is not valid base64.") from exc


def decode_wav_audio(audio_bytes: bytes) -> DecodedAudio:
    try:
        with wave.open(io.BytesIO(audio_bytes), "rb") as wav_file:
            channels = wav_file.getnchannels()
            sample_width_bytes = wav_file.getsampwidth()
            sample_rate_hz = wav_file.getframerate()
            frame_count = wav_file.getnframes()
            raw_frames = wav_file.readframes(frame_count)
    except wave.Error as exc:
        raise ValueError("Audio payload is not a valid WAV file.") from exc

    if channels <= 0 or sample_width_bytes <= 0:
        raise ValueError("Audio payload is missing channel or sample width information.")

    if sample_width_bytes not in {1, 2, 4}:
        raise ValueError("Only 8-bit, 16-bit, and 32-bit WAV PCM formats are supported.")

    samples_by_channel: list[list[float]] = [[] for _ in range(channels)]
    frame_stride = channels * sample_width_bytes

    for frame_offset in range(0, len(raw_frames), frame_stride):
        for channel_index in range(channels):
            sample_offset = frame_offset + (channel_index * sample_width_bytes)
            sample_bytes = raw_frames[sample_offset : sample_offset + sample_width_bytes]
            samples_by_channel[channel_index].append(_normalize_pcm_sample(sample_bytes, sample_width_bytes))

    return DecodedAudio(
        sample_rate_hz=sample_rate_hz,
        channels=channels,
        frame_count=frame_count,
        sample_width_bytes=sample_width_bytes,
        samples_by_channel=samples_by_channel,
    )


def _normalize_pcm_sample(sample_bytes: bytes, sample_width_bytes: int) -> float:
    if sample_width_bytes == 1:
        return (sample_bytes[0] - 128) / 128.0

    raw_value = int.from_bytes(sample_bytes, byteorder="little", signed=True)
    scale = float(1 << ((sample_width_bytes * 8) - 1))
    return raw_value / scale


def encode_wav_audio(decoded_audio: DecodedAudio, *, sample_width_bytes: int = 2) -> bytes:
    if sample_width_bytes != 2:
        raise ValueError("Only 16-bit WAV encoding is currently supported.")
    if decoded_audio.channels <= 0:
        raise ValueError("Decoded audio must contain at least one channel.")

    channel_lengths = [len(channel_samples) for channel_samples in decoded_audio.samples_by_channel]
    if not channel_lengths:
        raise ValueError("Decoded audio contains no sample data.")
    frame_count = min(channel_lengths)

    pcm_bytes = bytearray()
    for frame_index in range(frame_count):
        for channel_index in range(decoded_audio.channels):
            sample_value = decoded_audio.samples_by_channel[channel_index][frame_index]
            sample_value = max(-1.0, min(1.0, sample_value))
            quantized = int(sample_value * 32767.0) if sample_value >= 0 else int(sample_value * 32768.0)
            pcm_bytes.extend(int(quantized).to_bytes(2, byteorder="little", signed=True))

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(decoded_audio.channels)
        wav_file.setsampwidth(sample_width_bytes)
        wav_file.setframerate(decoded_audio.sample_rate_hz)
        wav_file.writeframes(bytes(pcm_bytes))
    return buffer.getvalue()
