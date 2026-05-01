from pathlib import Path

from raspirobot.actions import DefaultRobotActionDispatcher
from raspirobot.audio import (
    AudioListenWorker,
    EnergyVAD,
    EnergyVADConfig,
    FileAudioInputProvider,
    LocalCommandAudioOutputProvider,
    MockAudioInputProvider,
    MockAudioOutputProvider,
    make_silence_pcm,
    make_sine_pcm,
    write_wav,
)
from raspirobot.audio.preprocessor import AudioPreprocessor, AudioPreprocessConfig
from raspirobot.core import RaspiRobotRuntime, RobotRuntimeState, RobotStateMachine, TurnManager
from raspirobot.hardware import MockEyesDriver, MockHeadDriver
from raspirobot.remote import MockRemoteClient, RobotPayloadBuilder
from raspirobot.session import SessionManager, TurnLogger
from raspirobot.vision import MockVisionContextProvider


def _speech_wav(path: Path, *, channels: int = 2) -> Path:
    frames = [
        make_silence_pcm(duration_ms=300, channels=channels),
        make_sine_pcm(duration_ms=800, channels=channels, amplitude=6000),
        make_silence_pcm(duration_ms=1000, channels=channels),
    ]
    write_wav(path, frames, sample_rate=16000, channels=channels)
    return path


def test_payload_builder_creates_valid_robot_chat_request(tmp_path: Path) -> None:
    wav_path = _speech_wav(tmp_path / "input.wav", channels=2)
    builder = RobotPayloadBuilder(
        session_id="session-runtime",
        mode_id="care",
        vision_context_provider=MockVisionContextProvider(),
    )

    request = builder.build(wav_path=wav_path, turn_id="turn-0001")

    assert request.session_id == "session-runtime"
    assert request.turn_id == "turn-0001"
    assert request.input.type == "audio_base64"
    assert request.input.audio_base64
    assert request.input.sample_rate == 16000
    assert request.input.channels == 2
    assert request.input.duration_ms and request.input.duration_ms > 0
    assert request.vision_context is not None
    assert request.request_options["log_session_id"].startswith("cn-")
    assert request.request_options["log_timezone"] == "Asia/Shanghai"


def test_energy_vad_detects_speech_and_silence() -> None:
    vad = EnergyVAD(EnergyVADConfig(rms_threshold=500))
    provider = MockAudioInputProvider(
        [
            make_silence_pcm(duration_ms=30),
            make_sine_pcm(duration_ms=30, amplitude=6000),
        ]
    )
    frames = list(provider.frames())

    assert vad.is_voiced(frames[0]) is False
    assert vad.is_voiced(frames[1]) is True


def test_listener_saves_utterance_from_mock_frames(tmp_path: Path) -> None:
    frame_plan = []
    frame_plan.extend(make_silence_pcm(duration_ms=30) for _ in range(5))
    frame_plan.extend(make_sine_pcm(duration_ms=30, amplitude=6000) for _ in range(8))
    frame_plan.extend(make_silence_pcm(duration_ms=30) for _ in range(8))
    listener = AudioListenWorker(
        input_provider=MockAudioInputProvider(frame_plan),
        vad=EnergyVAD(
            EnergyVADConfig(
                rms_threshold=500,
                speech_start_frames=2,
                silence_timeout_ms=180,
                max_utterance_seconds=3,
                pre_roll_ms=60,
                frame_ms=30,
            )
        ),
        output_dir=tmp_path,
    )

    utterance = listener.listen_once()

    assert utterance is not None
    assert utterance.wav_path.exists()
    assert utterance.wav_info.duration_ms > 0


def test_runtime_transitions_through_one_file_turn(tmp_path: Path) -> None:
    wav_path = _speech_wav(tmp_path / "input.wav")
    eyes = MockEyesDriver()
    head = MockHeadDriver()
    audio = MockAudioOutputProvider()
    session = SessionManager(session_id="session-runtime", mode_id="care")
    turn_manager = TurnManager(
        payload_builder=RobotPayloadBuilder(
            session_id=session.session_id,
            mode_id=session.mode_id,
            vision_context_provider=MockVisionContextProvider(),
        ),
        remote_client=MockRemoteClient(),
        action_dispatcher=DefaultRobotActionDispatcher(eyes=eyes, head=head, audio=None),
        audio_output=audio,
        session=session,
        logger=TurnLogger(),
    )
    runtime = RaspiRobotRuntime(
        listener=AudioListenWorker(
            input_provider=FileAudioInputProvider(wav_path=wav_path),
            vad=EnergyVAD(EnergyVADConfig(rms_threshold=500, silence_timeout_ms=180)),
            output_dir=tmp_path / "utterances",
        ),
        turn_manager=turn_manager,
        state_machine=RobotStateMachine(mode_id="care"),
    )

    result = runtime.run_once()

    assert result.handled is True
    assert result.state == RobotRuntimeState.LISTENING
    assert result.turn is not None
    assert result.turn.response.success is True
    assert eyes.last_expression == "neutral"
    assert head.last_motion == "none"
    assert audio.played_urls == [None]


def test_local_audio_output_skips_missing_or_mock_tts_url(tmp_path: Path) -> None:
    player = LocalCommandAudioOutputProvider(command="aplay", download_dir=tmp_path)

    empty = player.play_audio_url(None)
    mock = player.play_audio_url("mock://tts/session/turn.wav")

    assert empty.played is False
    assert empty.skipped_reason == "empty audio_url"
    assert mock.played is False
    assert "mock" in (mock.skipped_reason or "")


def test_turn_manager_without_preprocessor_uses_raw_wav(tmp_path: Path) -> None:
    wav_path = _speech_wav(tmp_path / "input.wav")
    session = SessionManager(session_id="session-no-preproc", mode_id="care")
    turn_manager = TurnManager(
        payload_builder=RobotPayloadBuilder(
            session_id=session.session_id,
            mode_id=session.mode_id,
            vision_context_provider=MockVisionContextProvider(),
        ),
        remote_client=MockRemoteClient(),
        action_dispatcher=DefaultRobotActionDispatcher(eyes=MockEyesDriver(), head=MockHeadDriver(), audio=None),
        audio_output=MockAudioOutputProvider(),
        session=session,
        logger=TurnLogger(),
        audio_preprocessor=None,
    )

    result = turn_manager.handle_utterance(wav_path=wav_path)

    assert result.response.success is True
    assert result.response.asr_text is not None


def test_turn_manager_with_enabled_preprocessor_uses_clean_wav(tmp_path: Path) -> None:
    wav_path = _speech_wav(tmp_path / "input.wav")
    session = SessionManager(session_id="session-preproc-enabled", mode_id="care")
    preprocessor = AudioPreprocessor(
        AudioPreprocessConfig(
            enabled=True,
            enable_noise_gate=True,
            enable_trim=True,
        )
    )
    turn_manager = TurnManager(
        payload_builder=RobotPayloadBuilder(
            session_id=session.session_id,
            mode_id=session.mode_id,
            vision_context_provider=MockVisionContextProvider(),
        ),
        remote_client=MockRemoteClient(),
        action_dispatcher=DefaultRobotActionDispatcher(eyes=MockEyesDriver(), head=MockHeadDriver(), audio=None),
        audio_output=MockAudioOutputProvider(),
        session=session,
        logger=TurnLogger(),
        audio_preprocessor=preprocessor,
    )

    result = turn_manager.handle_utterance(wav_path=wav_path)

    assert result.response.success is True
    assert result.response.asr_text is not None
    clean_wav_path = wav_path.with_stem(f"{wav_path.stem}.clean")
    assert clean_wav_path.exists()


def test_turn_manager_gracefully_handles_preprocessor_exception(tmp_path: Path) -> None:
    wav_path = _speech_wav(tmp_path / "input.wav")
    session = SessionManager(session_id="session-preproc-exception", mode_id="care")

    class FailingPreprocessor(AudioPreprocessor):
        def process_file(self, wav_path, *, output_dir=None):
            raise RuntimeError("Simulated preprocessor failure")

    preprocessor = FailingPreprocessor()
    turn_manager = TurnManager(
        payload_builder=RobotPayloadBuilder(
            session_id=session.session_id,
            mode_id=session.mode_id,
            vision_context_provider=MockVisionContextProvider(),
        ),
        remote_client=MockRemoteClient(),
        action_dispatcher=DefaultRobotActionDispatcher(eyes=MockEyesDriver(), head=MockHeadDriver(), audio=None),
        audio_output=MockAudioOutputProvider(),
        session=session,
        logger=TurnLogger(),
        audio_preprocessor=preprocessor,
    )

    result = turn_manager.handle_utterance(wav_path=wav_path)

    assert result.response.success is True
    clean_wav_path = wav_path.with_stem(f"{wav_path.stem}.clean")
    assert not clean_wav_path.exists()
