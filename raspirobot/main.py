from __future__ import annotations

import argparse
from pathlib import Path

from raspirobot.actions import DefaultRobotActionDispatcher
from raspirobot.audio import (
    AudioInputProvider,
    AudioListenWorker,
    AudioOutputProvider,
    EnergyVAD,
    EnergyVADConfig,
    FileAudioInputProvider,
    LocalCommandAudioInputProvider,
    LocalCommandAudioOutputProvider,
    MockAudioOutputProvider,
)
from raspirobot.config import Settings, load_settings
from raspirobot.core import RaspiRobotRuntime, RobotStateMachine, TurnManager
from raspirobot.hardware import MockEyesDriver, MockHeadDriver
from raspirobot.remote import MockRemoteClient, RemoteClient, RemoteClientProtocol, RobotPayloadBuilder
from raspirobot.session import SessionManager, TurnLogger
from raspirobot.utils import ensure_dir
from raspirobot.vision import MockVisionContextProvider


def build_vad(settings: Settings) -> EnergyVAD:
    return EnergyVAD(
        EnergyVADConfig(
            rms_threshold=settings.vad_rms_threshold,
            speech_start_frames=settings.vad_speech_start_frames,
            silence_timeout_ms=settings.vad_silence_timeout_ms,
            max_utterance_seconds=settings.vad_max_utterance_seconds,
            pre_roll_ms=settings.vad_pre_roll_ms,
            frame_ms=settings.audio_frame_ms,
        )
    )


def build_live_input_provider(settings: Settings) -> AudioInputProvider:
    return LocalCommandAudioInputProvider(
        sample_rate=settings.audio_sample_rate,
        channels=settings.audio_channels,
        sample_width=settings.audio_sample_width,
        frame_ms=settings.audio_frame_ms,
        capture_device=settings.audio_capture_device,
        command=settings.audio_capture_command,
    )


def build_output_provider(settings: Settings, *, mock: bool = False) -> AudioOutputProvider:
    if mock or settings.audio_output_provider == "mock":
        return MockAudioOutputProvider()
    return LocalCommandAudioOutputProvider(
        command=settings.audio_playback_command,
        playback_device=settings.audio_playback_device,
        download_dir=Path(settings.audio_work_dir) / "playback",
    )


def build_runtime(
    *,
    input_provider: AudioInputProvider,
    remote_client: RemoteClientProtocol | None = None,
    audio_output: AudioOutputProvider | None = None,
    settings: Settings | None = None,
) -> RaspiRobotRuntime:
    settings = settings or load_settings()
    work_dir = ensure_dir(settings.audio_work_dir)
    session = SessionManager(session_id=settings.session_id, mode_id=settings.default_mode)
    output = audio_output or build_output_provider(settings)
    remote = remote_client or RemoteClient()
    dispatcher = DefaultRobotActionDispatcher(
        eyes=MockEyesDriver(),
        head=MockHeadDriver(),
        audio=None,
        remote_base_url=getattr(remote, "base_url", None),
    )
    payload_builder = RobotPayloadBuilder(
        session_id=settings.session_id,
        mode_id=settings.default_mode,
        vision_context_provider=MockVisionContextProvider(),
    )
    turn_manager = TurnManager(
        payload_builder=payload_builder,
        remote_client=remote,
        action_dispatcher=dispatcher,
        audio_output=output,
        session=session,
        logger=TurnLogger(work_dir / "turns.jsonl"),
    )
    listener = AudioListenWorker(
        input_provider=input_provider,
        vad=build_vad(settings),
        output_dir=work_dir / "utterances",
    )
    return RaspiRobotRuntime(
        listener=listener,
        turn_manager=turn_manager,
        state_machine=RobotStateMachine(mode_id=settings.default_mode),
        loop_sleep_seconds=settings.live_loop_sleep_seconds,
    )


def run_file_once(wav_path: str, *, use_mock_remote: bool = True, mock_playback: bool = True) -> None:
    settings = load_settings()
    runtime = build_runtime(
        input_provider=FileAudioInputProvider(wav_path=wav_path, frame_ms=settings.audio_frame_ms),
        remote_client=MockRemoteClient() if use_mock_remote else RemoteClient(),
        audio_output=build_output_provider(settings, mock=mock_playback),
        settings=settings,
    )
    result = runtime.run_once()
    if result.turn:
        print(f"state={result.state.value}")
        print(f"asr_text={result.turn.response.asr_text}")
        print(f"reply_text={result.turn.response.reply_text}")
        print(f"playback={result.turn.playback}")
    else:
        print(f"state={result.state.value}")
        print(f"handled={result.handled}")
        print(f"error={result.error}")


def run_live_loop() -> None:
    settings = load_settings()
    runtime = build_runtime(input_provider=build_live_input_provider(settings), settings=settings)
    runtime.run_forever()


def main() -> None:
    parser = argparse.ArgumentParser(description="RobotMatch Raspberry Pi runtime")
    subparsers = parser.add_subparsers(dest="command", required=True)

    file_parser = subparsers.add_parser("file-once", help="Run one VAD turn from a wav file.")
    file_parser.add_argument("--wav", required=True)
    file_parser.add_argument("--real-remote", action="store_true")
    file_parser.add_argument("--local-playback", action="store_true")

    subparsers.add_parser("live", help="Run continuous microphone listening loop.")

    args = parser.parse_args()
    if args.command == "file-once":
        run_file_once(
            args.wav,
            use_mock_remote=not args.real_remote,
            mock_playback=not args.local_playback,
        )
    elif args.command == "live":
        run_live_loop()


if __name__ == "__main__":
    main()
