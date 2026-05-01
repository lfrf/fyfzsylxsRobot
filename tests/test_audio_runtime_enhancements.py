"""
Tests for audio runtime enhancements: cooldown, invalid utterance drop, and payload logging.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from raspirobot.config import Settings, load_settings
from raspirobot.core.turn_manager import TurnManager, UtteranceRejected
from raspirobot.audio.preprocessor import AudioPreprocessConfig, AudioPreprocessor
from raspirobot.audio import MockAudioOutputProvider
from raspirobot.actions import DefaultRobotActionDispatcher
from raspirobot.hardware import MockEyesDriver, MockHeadDriver
from raspirobot.remote import MockRemoteClient, RobotPayloadBuilder
from raspirobot.session import SessionManager, TurnLogger
from raspirobot.vision import MockVisionContextProvider
import wave


def write_test_wav(
    path: str | Path,
    samples: np.ndarray | list[int] | bytes,
    *,
    sample_rate: int = 16000,
    channels: int = 1,
    sample_width: int = 2,
) -> Path:
    """Helper to create test WAV files."""
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


class TestConfigEnhancements:
    """Test new configuration fields for cooldown and invalid utterance drop."""

    def test_load_settings_post_playback_cooldown_ms_default(self, monkeypatch):
        """Test default value for post-playback cooldown."""
        monkeypatch.delenv("ROBOT_AUDIO_POST_PLAYBACK_COOLDOWN_MS", raising=False)
        settings = load_settings()
        assert settings.audio_post_playback_cooldown_ms == 0

    def test_load_settings_post_playback_cooldown_ms_custom(self, monkeypatch):
        """Test custom value for post-playback cooldown."""
        monkeypatch.setenv("ROBOT_AUDIO_POST_PLAYBACK_COOLDOWN_MS", "800")
        settings = load_settings()
        assert settings.audio_post_playback_cooldown_ms == 800

    def test_load_settings_drop_invalid_utterance_default(self, monkeypatch):
        """Test default value for drop invalid utterance."""
        monkeypatch.delenv("ROBOT_AUDIO_DROP_INVALID_UTTERANCE", raising=False)
        settings = load_settings()
        assert settings.audio_drop_invalid_utterance is False

    def test_load_settings_drop_invalid_utterance_enabled(self, monkeypatch):
        """Test enabled value for drop invalid utterance."""
        monkeypatch.setenv("ROBOT_AUDIO_DROP_INVALID_UTTERANCE", "true")
        settings = load_settings()
        assert settings.audio_drop_invalid_utterance is True

    def test_load_settings_drop_reasons_default(self, monkeypatch):
        """Test default value for drop reasons."""
        monkeypatch.delenv("ROBOT_AUDIO_DROP_REASONS", raising=False)
        settings = load_settings()
        assert settings.audio_drop_reasons == "no_speech_detected,speech_too_short"

    def test_load_settings_drop_reasons_custom(self, monkeypatch):
        """Test custom value for drop reasons."""
        monkeypatch.setenv("ROBOT_AUDIO_DROP_REASONS", "no_speech_detected,invalid_trim_range")
        settings = load_settings()
        assert settings.audio_drop_reasons == "no_speech_detected,invalid_trim_range"


class TestUtteranceDropLogic:
    """Test invalid utterance drop mechanism."""

    def test_turn_manager_drop_no_speech_detected(self, tmp_path: Path, monkeypatch):
        """Test that utterances with no_speech_detected are dropped when enabled."""
        wav_path = write_test_wav(tmp_path / "silent.wav", np.zeros(16000, dtype=np.int16))
        session = SessionManager(session_id="test-drop", mode_id="care")
        
        # Create preprocessor that produces no_speech_detected fallback
        preprocessor = AudioPreprocessor(
            AudioPreprocessConfig(enabled=True, enable_noise_gate=True, enable_trim=True)
        )
        
        turn_manager = TurnManager(
            payload_builder=RobotPayloadBuilder(
                session_id=session.session_id,
                mode_id=session.mode_id,
                vision_context_provider=MockVisionContextProvider(),
            ),
            remote_client=MockRemoteClient(),
            action_dispatcher=DefaultRobotActionDispatcher(
                eyes=MockEyesDriver(), head=MockHeadDriver(), audio=None
            ),
            audio_output=MockAudioOutputProvider(),
            session=session,
            logger=TurnLogger(),
            audio_preprocessor=preprocessor,
            audio_drop_invalid_utterance=True,
            audio_drop_reasons="no_speech_detected,speech_too_short",
        )

        # Should raise UtteranceRejected
        with pytest.raises(UtteranceRejected, match="no_speech_detected"):
            turn_manager.handle_utterance(wav_path)

    def test_turn_manager_keep_utterance_when_drop_disabled(self, tmp_path: Path):
        """Test that utterances are kept when drop is disabled."""
        wav_path = write_test_wav(tmp_path / "silence2.wav", np.zeros(16000, dtype=np.int16))
        session = SessionManager(session_id="test-keep", mode_id="care")
        
        preprocessor = AudioPreprocessor(
            AudioPreprocessConfig(enabled=True, enable_noise_gate=True, enable_trim=True)
        )
        
        turn_manager = TurnManager(
            payload_builder=RobotPayloadBuilder(
                session_id=session.session_id,
                mode_id=session.mode_id,
                vision_context_provider=MockVisionContextProvider(),
            ),
            remote_client=MockRemoteClient(),
            action_dispatcher=DefaultRobotActionDispatcher(
                eyes=MockEyesDriver(), head=MockHeadDriver(), audio=None
            ),
            audio_output=MockAudioOutputProvider(),
            session=session,
            logger=TurnLogger(),
            audio_preprocessor=preprocessor,
            audio_drop_invalid_utterance=False,  # Disabled
            audio_drop_reasons="no_speech_detected,speech_too_short",
        )

        # Should NOT raise, just fallback to raw
        result = turn_manager.handle_utterance(wav_path)
        assert result.response is not None

    def test_turn_manager_without_preprocessor_no_drop(self, tmp_path: Path):
        """Test that drop mechanism doesn't activate without preprocessor."""
        wav_path = write_test_wav(tmp_path / "input3.wav", np.full(16000, 1000, dtype=np.int16))
        session = SessionManager(session_id="test-nodrop", mode_id="care")
        
        turn_manager = TurnManager(
            payload_builder=RobotPayloadBuilder(
                session_id=session.session_id,
                mode_id=session.mode_id,
                vision_context_provider=MockVisionContextProvider(),
            ),
            remote_client=MockRemoteClient(),
            action_dispatcher=DefaultRobotActionDispatcher(
                eyes=MockEyesDriver(), head=MockHeadDriver(), audio=None
            ),
            audio_output=MockAudioOutputProvider(),
            session=session,
            logger=TurnLogger(),
            audio_preprocessor=None,  # No preprocessor
            audio_drop_invalid_utterance=True,
            audio_drop_reasons="no_speech_detected,speech_too_short",
        )

        # Should work normally (drop only applies to preprocess results)
        result = turn_manager.handle_utterance(wav_path)
        assert result.response is not None


class TestAudioPayloadSelection:
    """Test audio payload selection logging."""

    def test_audio_payload_selected_with_preprocessor(self, tmp_path: Path):
        """Test audio_payload_selected event with preprocessor enabled."""
        samples = np.full(16000, 2000, dtype=np.int16)
        wav_path = write_test_wav(tmp_path / "speech.wav", samples)
        session = SessionManager(session_id="test-payload", mode_id="care")
        
        preprocessor = AudioPreprocessor(
            AudioPreprocessConfig(enabled=True, enable_noise_gate=True)
        )
        
        with patch("raspirobot.core.turn_manager.log_event") as mock_log:
            turn_manager = TurnManager(
                payload_builder=RobotPayloadBuilder(
                    session_id=session.session_id,
                    mode_id=session.mode_id,
                    vision_context_provider=MockVisionContextProvider(),
                ),
                remote_client=MockRemoteClient(),
                action_dispatcher=DefaultRobotActionDispatcher(
                    eyes=MockEyesDriver(), head=MockHeadDriver(), audio=None
                ),
                audio_output=MockAudioOutputProvider(),
                session=session,
                logger=TurnLogger(),
                audio_preprocessor=preprocessor,
            )
            
            result = turn_manager.handle_utterance(wav_path)
            
            # Check that audio_payload_selected was logged
            payload_selected_calls = [
                call for call in mock_log.call_args_list
                if len(call[0]) > 0 and call[0][0] == "audio_payload_selected"
            ]
            assert len(payload_selected_calls) > 0
            
            # Verify event has required fields
            event_kwargs = payload_selected_calls[0][1]
            assert "payload_wav_path" in event_kwargs
            assert "preprocess_enabled" in event_kwargs
            assert "preprocess_fallback_used" in event_kwargs
            assert "noise_floor_rms" in event_kwargs

    def test_audio_payload_selected_without_preprocessor(self, tmp_path: Path):
        """Test audio_payload_selected event without preprocessor."""
        samples = np.full(16000, 2000, dtype=np.int16)
        wav_path = write_test_wav(tmp_path / "speech2.wav", samples)
        session = SessionManager(session_id="test-payload-no-prep", mode_id="care")
        
        with patch("raspirobot.core.turn_manager.log_event") as mock_log:
            turn_manager = TurnManager(
                payload_builder=RobotPayloadBuilder(
                    session_id=session.session_id,
                    mode_id=session.mode_id,
                    vision_context_provider=MockVisionContextProvider(),
                ),
                remote_client=MockRemoteClient(),
                action_dispatcher=DefaultRobotActionDispatcher(
                    eyes=MockEyesDriver(), head=MockHeadDriver(), audio=None
                ),
                audio_output=MockAudioOutputProvider(),
                session=session,
                logger=TurnLogger(),
                audio_preprocessor=None,
            )
            
            result = turn_manager.handle_utterance(wav_path)
            
            # Check that audio_payload_selected was logged
            payload_selected_calls = [
                call for call in mock_log.call_args_list
                if len(call[0]) > 0 and call[0][0] == "audio_payload_selected"
            ]
            assert len(payload_selected_calls) > 0
            
            # Verify event indicates no preprocessing
            event_kwargs = payload_selected_calls[0][1]
            assert event_kwargs.get("preprocess_enabled") is False
            assert event_kwargs.get("payload_wav_path") == str(wav_path)


class TestCooldownConfiguration:
    """Test post-playback cooldown configuration."""

    def test_runtime_accepts_cooldown_ms_parameter(self):
        """Test that runtime accepts post_playback_cooldown_ms parameter."""
        from raspirobot.core.runtime import RaspiRobotRuntime
        from raspirobot.audio import AudioListenWorker, EnergyVAD, EnergyVADConfig
        from raspirobot.core.state_machine import RobotStateMachine
        
        listener = AudioListenWorker(
            input_provider=MagicMock(),
            vad=EnergyVAD(EnergyVADConfig()),
            output_dir=Path("/tmp"),
        )
        
        runtime = RaspiRobotRuntime(
            listener=listener,
            turn_manager=MagicMock(),
            state_machine=RobotStateMachine(),
            post_playback_cooldown_ms=800,
        )
        
        assert runtime.post_playback_cooldown_ms == 800

    def test_runtime_default_cooldown_zero(self):
        """Test that runtime defaults to zero cooldown."""
        from raspirobot.core.runtime import RaspiRobotRuntime
        from raspirobot.audio import AudioListenWorker, EnergyVAD, EnergyVADConfig
        from raspirobot.core.state_machine import RobotStateMachine
        
        listener = AudioListenWorker(
            input_provider=MagicMock(),
            vad=EnergyVAD(EnergyVADConfig()),
            output_dir=Path("/tmp"),
        )
        
        runtime = RaspiRobotRuntime(
            listener=listener,
            turn_manager=MagicMock(),
            state_machine=RobotStateMachine(),
        )
        
        assert runtime.post_playback_cooldown_ms == 0
