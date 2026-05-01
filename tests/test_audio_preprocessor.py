from __future__ import annotations

import wave
from pathlib import Path

import numpy as np
import pytest

from raspirobot.audio.preprocessor import AudioPreprocessConfig, AudioPreprocessor


def write_test_wav(
    path: str | Path,
    samples: np.ndarray | list[int] | bytes,
    *,
    sample_rate: int = 16000,
    channels: int = 1,
    sample_width: int = 2,
) -> Path:
    wav_path = Path(path)
    wav_path.parent.mkdir(parents=True, exist_ok=True)

    if isinstance(samples, bytes):
        pcm = samples
    else:
        array = np.asarray(samples)
        if sample_width == 2:
            if channels > 1 and array.ndim == 1:
                array = np.repeat(array[:, None], channels, axis=1)
            pcm = array.astype("<i2", copy=False).tobytes()
        elif sample_width == 1:
            if channels > 1 and array.ndim == 1:
                array = np.repeat(array[:, None], channels, axis=1)
            pcm = array.astype("uint8", copy=False).tobytes()
        else:
            raise ValueError("This helper only supports 8-bit or 16-bit PCM")

    with wave.open(str(wav_path), "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(sample_width)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm)
    return wav_path


def test_disabled_mode_returns_raw_wav_path(tmp_path: Path) -> None:
    wav_path = write_test_wav(tmp_path / "input.wav", np.zeros(1600, dtype=np.int16))
    preprocessor = AudioPreprocessor(AudioPreprocessConfig(enabled=False))

    result = preprocessor.process_file(wav_path, output_dir=tmp_path)

    assert result.raw_wav_path == wav_path
    assert result.used_for_payload_path == wav_path
    assert result.clean_wav_path is None
    assert result.fallback_used is True
    assert result.fallback_reason == "disabled"


def test_mono_16bit_wav_loads(tmp_path: Path) -> None:
    samples = np.full(16000, 1200, dtype=np.int16)
    wav_path = write_test_wav(tmp_path / "mono.wav", samples)
    preprocessor = AudioPreprocessor(AudioPreprocessConfig(enabled=True))

    result = preprocessor.process_file(wav_path, output_dir=tmp_path)

    assert result.raw_wav_path == wav_path
    assert result.raw_duration_ms > 0
    assert result.total_frames > 0
    assert result.speech_peak_rms > 0
    assert result.speech_mean_rms > 0
    assert result.noise_floor_rms >= 0
    assert result.noise_floor_strategy in {"initial_calibration", "global_low_percentile", "short_audio_percentile"}
    assert result.gate_threshold_rms >= 80
    assert result.fallback_used is False
    assert result.clean_wav_path is not None
    assert result.clean_wav_path.exists()
    assert result.used_for_payload_path == result.clean_wav_path
    assert result.clean_wav_path.name == "mono.clean.wav"
    assert result.clean_duration_ms is not None
    assert result.clean_duration_ms > 0
    assert result.debug_json_path is not None
    assert result.debug_json_path.exists()
    assert result.debug_json_path.name == "mono.debug.json"


def test_stereo_16bit_wav_loads(tmp_path: Path) -> None:
    samples = np.column_stack([
        np.zeros(16000, dtype=np.int16),
        np.full(16000, 500, dtype=np.int16),
    ])
    wav_path = write_test_wav(tmp_path / "stereo.wav", samples, channels=2)
    preprocessor = AudioPreprocessor(AudioPreprocessConfig(enabled=True))

    result = preprocessor.process_file(wav_path, output_dir=tmp_path)

    assert result.raw_wav_path == wav_path
    assert result.total_frames > 0
    assert result.raw_duration_ms > 0


def test_unsupported_sample_width_raises_value_error(tmp_path: Path) -> None:
    wav_path = write_test_wav(tmp_path / "bad.wav", np.full(1600, 128, dtype=np.uint8), sample_width=1)
    preprocessor = AudioPreprocessor(AudioPreprocessConfig(enabled=True))

    with pytest.raises(ValueError, match="Unsupported wav sample width"):
        preprocessor.process_file(wav_path, output_dir=tmp_path)


def test_all_silence_wav_does_not_crash(tmp_path: Path) -> None:
    wav_path = write_test_wav(tmp_path / "silence.wav", np.zeros(1600, dtype=np.int16))
    preprocessor = AudioPreprocessor(AudioPreprocessConfig(enabled=True))

    result = preprocessor.process_file(wav_path, output_dir=tmp_path)

    assert result.raw_wav_path == wav_path
    assert result.total_frames > 0
    assert result.raw_duration_ms > 0
    assert result.speech_frames == 0
    assert result.fallback_used is True
    assert result.fallback_reason == "no_speech_detected"
    assert result.clean_wav_path is None
    assert result.used_for_payload_path == wav_path
    assert result.debug_json_path is not None
    assert result.debug_json_path.exists()