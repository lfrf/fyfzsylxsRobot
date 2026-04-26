from math import sqrt

from models import AudioMeta, SpeechFeatures
from services.wav_utils import DecodedAudio


class AudioFeatureExtractor:
    def extract(
        self,
        decoded_audio: DecodedAudio,
        *,
        audio_format: str | None,
        transcript: str,
        transcript_confidence: float | None,
    ) -> tuple[AudioMeta, SpeechFeatures]:
        duration_seconds = (
            decoded_audio.frame_count / decoded_audio.sample_rate_hz if decoded_audio.sample_rate_hz else 0.0
        )
        duration_ms = round(duration_seconds * 1000)

        if not decoded_audio.samples_by_channel:
            return (
                AudioMeta(
                    format=audio_format,
                    duration_ms=duration_ms,
                    sample_rate_hz=decoded_audio.sample_rate_hz,
                    channels=decoded_audio.channels,
                    frame_count=decoded_audio.frame_count,
                    source="remote_speech_service",
                ),
                SpeechFeatures(
                    transcript_confidence=transcript_confidence,
                    source="remote_speech_service",
                ),
            )

        channel_rms_levels = [_round_or_none(_compute_rms(samples)) or 0.0 for samples in decoded_audio.samples_by_channel]
        dominant_channel = channel_rms_levels.index(max(channel_rms_levels)) + 1 if channel_rms_levels else None
        primary_channel = decoded_audio.samples_by_channel[(dominant_channel or 1) - 1]

        speaking_rate = _estimate_speaking_rate(transcript, duration_seconds)
        pause_ratio = _estimate_pause_ratio(primary_channel, decoded_audio.sample_rate_hz)
        rms_energy = _round_or_none(_compute_rms(primary_channel))
        peak_level = _round_or_none(max((abs(sample) for sample in primary_channel), default=0.0))
        pitch_hz = _estimate_pitch(primary_channel, decoded_audio.sample_rate_hz, duration_seconds)
        emotion_tags = _infer_emotion_tags(
            speaking_rate=speaking_rate,
            pause_ratio=pause_ratio,
            rms_energy=rms_energy,
        )

        return (
            AudioMeta(
                format=audio_format,
                duration_ms=duration_ms,
                sample_rate_hz=decoded_audio.sample_rate_hz,
                channels=decoded_audio.channels,
                frame_count=decoded_audio.frame_count,
                source="remote_speech_service",
            ),
            SpeechFeatures(
                transcript_confidence=transcript_confidence,
                speaking_rate=speaking_rate,
                pause_ratio=pause_ratio,
                rms_energy=rms_energy,
                peak_level=peak_level,
                pitch_hz=pitch_hz,
                dominant_channel=dominant_channel,
                emotion_tags=emotion_tags,
                channel_rms_levels=[round(level, 4) for level in channel_rms_levels],
                source="remote_speech_service",
            ),
        )


def _compute_rms(samples: list[float]) -> float | None:
    if not samples:
        return None
    return sqrt(sum(sample * sample for sample in samples) / len(samples))


def _estimate_speaking_rate(transcript: str, duration_seconds: float) -> float | None:
    if not transcript or duration_seconds <= 0:
        return None
    token_count = len([token for token in transcript.split() if token]) or len("".join(transcript.split()))
    return round(token_count / duration_seconds, 2) if token_count > 0 else None


def _estimate_pause_ratio(samples: list[float], sample_rate_hz: int) -> float | None:
    if not samples or sample_rate_hz <= 0:
        return None

    window_size = max(int(sample_rate_hz * 0.05), 1)
    silent_windows = 0
    total_windows = 0
    for offset in range(0, len(samples), window_size):
        window = samples[offset : offset + window_size]
        if not window:
            continue
        average_energy = sum(abs(sample) for sample in window) / len(window)
        if average_energy < 0.015:
            silent_windows += 1
        total_windows += 1

    return round(silent_windows / total_windows, 4) if total_windows > 0 else None


def _estimate_pitch(samples: list[float], sample_rate_hz: int, duration_seconds: float) -> float | None:
    if len(samples) < 2 or sample_rate_hz <= 0 or duration_seconds <= 0:
        return None

    zero_crossings = 0
    previous = samples[0]
    for current in samples[1:]:
        crossed_up = previous <= 0 < current
        crossed_down = previous >= 0 > current
        if crossed_up or crossed_down:
            zero_crossings += 1
        previous = current

    return round(zero_crossings / (2 * duration_seconds), 2) if zero_crossings > 0 else None


def _infer_emotion_tags(*, speaking_rate: float | None, pause_ratio: float | None, rms_energy: float | None) -> list[str]:
    tags: list[str] = []
    if pause_ratio is not None and pause_ratio >= 0.35:
        tags.append("hesitant")
    if rms_energy is not None and rms_energy <= 0.035:
        tags.append("fatigued")
    elif rms_energy is not None and rms_energy >= 0.18:
        tags.append("energized")
    if speaking_rate is not None and speaking_rate >= 5.5:
        tags.append("agitated")
    elif speaking_rate is not None and speaking_rate <= 2.2:
        tags.append("calm")
    if not tags:
        tags.append("steady")
    return tags


def _round_or_none(value: float | None) -> float | None:
    return round(value, 4) if value is not None else None


audio_feature_extractor = AudioFeatureExtractor()
