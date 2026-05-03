from __future__ import annotations

import argparse
import logging
import threading
from pathlib import Path
from typing import Any

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
from raspirobot.audio.preprocessor import AudioPreprocessor, AudioPreprocessConfig
from raspirobot.config import Settings, load_settings
from raspirobot.core import RaspiRobotRuntime, RobotStateMachine, TurnManager
from raspirobot.hardware import MockEyesDriver, MockHeadDriver, ST7789EyeConfig, ST7789EyesDriver
from raspirobot.remote import MockRemoteClient, RemoteClient, RemoteClientProtocol, RobotPayloadBuilder
from raspirobot.session import SessionManager, TurnLogger
from raspirobot.utils import ensure_dir
from raspirobot.vision import MockVisionContextProvider
from shared.logging_utils import get_log_file_path, get_log_session_id, log_event, start_log_session

logger = logging.getLogger(__name__)


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


def build_audio_preprocessor(settings: Settings) -> AudioPreprocessor | None:
    if not settings.audio_preprocess_enabled:
        return None
    config = AudioPreprocessConfig(
        enabled=settings.audio_preprocess_enabled,
        enable_noise_gate=settings.audio_enable_noise_gate,
        enable_trim=settings.audio_enable_trim,
        frame_ms=settings.audio_frame_ms,
        min_speech_ms=settings.audio_min_speech_ms,
        post_speech_padding_ms=settings.audio_post_speech_padding_ms,
        noise_calibration_ms=settings.audio_noise_calibration_ms,
        noise_gate_ratio=settings.audio_noise_gate_ratio,
        min_rms=settings.audio_min_rms,
        save_debug_wav=settings.audio_save_debug_wav,
        debug_dir=Path(settings.audio_work_dir) / "preprocessor_debug" if settings.audio_save_debug_wav else None,
    )
    return AudioPreprocessor(config)


def build_eyes_driver(settings: Settings) -> MockEyesDriver | ST7789EyesDriver:
    if settings.eyes_provider != "st7789":
        return MockEyesDriver()
    try:
        base_assets = Path(settings.eyes_assets_dir)
        left_assets = Path(settings.eyes_left_assets_dir) if settings.eyes_left_assets_dir else None
        right_assets = Path(settings.eyes_right_assets_dir) if settings.eyes_right_assets_dir else None
        return ST7789EyesDriver(
            ST7789EyeConfig(
                assets_dir=base_assets,
                fps=settings.eyes_frame_fps,
                width=settings.eyes_screen_width,
                height=settings.eyes_screen_height,
                rotation=settings.eyes_rotation,
                spi_port=settings.eyes_spi_port,
                right_spi_port=settings.eyes_right_spi_port,
                spi_speed_hz=settings.eyes_spi_speed_hz,
                rst_gpio=settings.eyes_rst_gpio,
                left_dc_gpio=settings.eyes_left_dc_gpio,
                right_dc_gpio=settings.eyes_right_dc_gpio,
                left_cs=settings.eyes_left_cs,
                right_cs=settings.eyes_right_cs,
                right_enabled=settings.eyes_right_enabled,
                left_assets_dir=left_assets,
                right_assets_dir=right_assets,
                gpio_chip=settings.eyes_gpio_chip,
                left_rotation=settings.eyes_left_rotation,
                right_rotation=settings.eyes_right_rotation,
            )
        )
    except Exception as exc:
        logger.warning("failed_to_init_st7789_eyes; fallback_to_mock: %s", exc)
        return MockEyesDriver()


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
        eyes=build_eyes_driver(settings),
        head=MockHeadDriver(),
        audio=None,
        remote_base_url=getattr(remote, "base_url", None),
    )
    payload_builder = RobotPayloadBuilder(
        session_id=settings.session_id,
        mode_id=settings.default_mode,
        vision_context_provider=MockVisionContextProvider(),
    )
    audio_preprocessor = build_audio_preprocessor(settings)
    turn_manager = TurnManager(
        payload_builder=payload_builder,
        remote_client=remote,
        action_dispatcher=dispatcher,
        audio_output=output,
        session=session,
        logger=TurnLogger(work_dir / "turns.jsonl"),
        audio_preprocessor=audio_preprocessor,
        audio_drop_invalid_utterance=settings.audio_drop_invalid_utterance,
        audio_drop_reasons=settings.audio_drop_reasons,
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
        post_playback_cooldown_ms=settings.audio_post_playback_cooldown_ms,
    )


def run_file_once(wav_path: str, *, use_mock_remote: bool = True, mock_playback: bool = True) -> None:
    settings = load_settings()
    start_raspi_runtime_log("file_once", settings)
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
    start_raspi_runtime_log("live_audio_loop", settings)
    runtime = build_runtime(input_provider=build_live_input_provider(settings), settings=settings)
    runtime.run_forever()


def _start_face_tracking_for_live(args: argparse.Namespace) -> tuple[Any, threading.Thread] | None:
    if not getattr(args, "face_track", False):
        return None

    try:
        from raspirobot.hardware.pan_tilt_face_tracker import (
            CameraCapture,
            CameraConfig,
            FaceDetector,
            FaceTrackingPanTiltRunner,
            PanTiltServoConfig,
            PanTiltServoDriver,
            ServoSpec,
            TrackerConfig,
        )
    except Exception as exc:  # pragma: no cover - depends on hardware runtime
        print(f"[live] face tracking disabled: import failed: {exc}")
        return None

    try:
        pan_spec = ServoSpec(
            model_name="LD-3015MG",
            min_pulse_us=args.face_track_servo_min_pulse,
            max_pulse_us=args.face_track_servo_max_pulse,
            actuation_range_deg=args.face_track_actuation_range,
            safe_min_angle_deg=args.face_track_pan_min_angle,
            safe_max_angle_deg=args.face_track_pan_max_angle,
            center_angle_deg=args.face_track_center_pan,
        )
        tilt_spec = ServoSpec(
            model_name="LD-3015MG",
            min_pulse_us=args.face_track_servo_min_pulse,
            max_pulse_us=args.face_track_servo_max_pulse,
            actuation_range_deg=args.face_track_actuation_range,
            safe_min_angle_deg=args.face_track_tilt_min_angle,
            safe_max_angle_deg=args.face_track_tilt_max_angle,
            center_angle_deg=args.face_track_center_tilt,
        )

        servo_cfg = PanTiltServoConfig(
            i2c_address=args.face_track_i2c_address,
            frequency_hz=args.face_track_frequency,
            pan_channel=args.face_track_pan_channel,
            tilt_channel=args.face_track_tilt_channel,
            pan_inverted=args.face_track_pan_inverted,
            tilt_inverted=args.face_track_tilt_inverted,
            pan_zero_offset_deg=args.face_track_pan_zero_offset,
            tilt_zero_offset_deg=args.face_track_tilt_zero_offset,
            pan_spec=pan_spec,
            tilt_spec=tilt_spec,
        )
        camera_cfg = CameraConfig(
            width=args.face_track_camera_width,
            height=args.face_track_camera_height,
            use_picamera2=not args.face_track_no_picamera2,
            cv2_device_index=args.face_track_device_index,
        )
        tracker_cfg = TrackerConfig(
            detect_scale=args.face_track_detect_scale,
            min_face_size=args.face_track_min_face_size,
        )

        servo = PanTiltServoDriver(servo_cfg)
        camera = CameraCapture(camera_cfg)
        detector = FaceDetector(
            detector_mode=args.face_track_detector,
            min_face_size=args.face_track_min_face_size,
            min_detection_confidence=args.face_track_min_detection_confidence,
            haar_scale_factor=args.face_track_haar_scale_factor,
            haar_min_neighbors=args.face_track_haar_min_neighbors,
        )
        runner = FaceTrackingPanTiltRunner(
            servo=servo,
            camera=camera,
            detector=detector,
            config=tracker_cfg,
            show_window=args.face_track_window,
        )
    except Exception as exc:  # pragma: no cover - depends on hardware runtime
        print(f"[live] face tracking disabled: startup failed: {exc}")
        return None

    thread = threading.Thread(target=runner.run, daemon=True, name="face-tracking")
    thread.start()
    print("[live] face tracking started in background thread")
    return runner, thread


def run_live_loop_with_optional_face_tracking(args: argparse.Namespace) -> None:
    settings = load_settings()
    start_raspi_runtime_log("live_audio_loop", settings)
    runtime = build_runtime(input_provider=build_live_input_provider(settings), settings=settings)
    runner_thread = _start_face_tracking_for_live(args)

    try:
        runtime.run_forever()
    except KeyboardInterrupt:
        print("[live] interrupted by user")
    finally:
        if runner_thread is not None:
            runner, worker = runner_thread
            print("[live] stopping face tracking...")
            runner.request_stop()
            worker.join(timeout=3.0)


def start_raspi_runtime_log(runtime_name: str, settings: Settings) -> str:
    log_session_id = start_log_session()
    log_event(
        "raspi_runtime_log_session_started",
        component="raspirobot",
        runtime=runtime_name,
        log_session_id=log_session_id,
        log_timezone="Asia/Shanghai",
        log_file_path=get_log_file_path(),
        robot_session_id=settings.session_id,
        remote_base_url=settings.remote_base_url,
        chat_endpoint=settings.chat_endpoint,
        audio_capture_provider=settings.audio_capture_provider,
        audio_output_provider=settings.audio_output_provider,
        audio_capture_device=settings.audio_capture_device,
        audio_playback_device=settings.audio_playback_device,
        sample_rate=settings.audio_sample_rate,
        channels=settings.audio_channels,
        default_mode=settings.default_mode,
    )
    return get_log_session_id()


def main() -> None:
    parser = argparse.ArgumentParser(description="RobotMatch Raspberry Pi runtime")
    subparsers = parser.add_subparsers(dest="command", required=True)

    file_parser = subparsers.add_parser("file-once", help="Run one VAD turn from a wav file.")
    file_parser.add_argument("--wav", required=True)
    file_parser.add_argument("--real-remote", action="store_true")
    file_parser.add_argument("--local-playback", action="store_true")

    live_parser = subparsers.add_parser("live", help="Run continuous microphone listening loop.")
    live_parser.add_argument("--face-track", action="store_true", help="Enable pan-tilt face tracking in background.")
    live_parser.add_argument("--face-track-window", action="store_true", help="Show tracking window for debugging.")
    live_parser.add_argument("--face-track-detector", choices=["auto", "haar", "mediapipe"], default="auto")
    live_parser.add_argument("--face-track-min-detection-confidence", type=float, default=0.55)
    live_parser.add_argument("--face-track-haar-scale-factor", type=float, default=1.08)
    live_parser.add_argument("--face-track-haar-min-neighbors", type=int, default=4)
    live_parser.add_argument("--face-track-detect-scale", type=float, default=1.0)
    live_parser.add_argument("--face-track-min-face-size", type=int, default=28)
    live_parser.add_argument("--face-track-camera-width", type=int, default=320)
    live_parser.add_argument("--face-track-camera-height", type=int, default=240)
    live_parser.add_argument("--face-track-no-picamera2", action="store_true", help="Use cv2.VideoCapture backend.")
    live_parser.add_argument("--face-track-device-index", type=int, default=0)
    live_parser.add_argument("--face-track-pan-channel", type=int, default=0)
    live_parser.add_argument("--face-track-tilt-channel", type=int, default=1)
    live_parser.add_argument("--face-track-i2c-address", type=lambda x: int(x, 0), default=0x40)
    live_parser.add_argument("--face-track-frequency", type=int, default=50)
    live_parser.add_argument("--face-track-servo-min-pulse", type=int, default=500)
    live_parser.add_argument("--face-track-servo-max-pulse", type=int, default=2500)
    live_parser.add_argument("--face-track-actuation-range", type=float, default=270.0)
    live_parser.add_argument("--face-track-center-pan", type=float, default=135.0)
    live_parser.add_argument("--face-track-center-tilt", type=float, default=135.0)
    live_parser.add_argument("--face-track-pan-min-angle", type=float, default=0.0)
    live_parser.add_argument("--face-track-pan-max-angle", type=float, default=270.0)
    live_parser.add_argument("--face-track-tilt-min-angle", type=float, default=35.0)
    live_parser.add_argument("--face-track-tilt-max-angle", type=float, default=235.0)
    live_parser.add_argument("--face-track-pan-zero-offset", type=float, default=0.0)
    live_parser.add_argument("--face-track-tilt-zero-offset", type=float, default=0.0)
    live_parser.set_defaults(face_track_pan_inverted=True, face_track_tilt_inverted=True)
    live_parser.add_argument(
        "--face-track-pan-inverted",
        dest="face_track_pan_inverted",
        action="store_true",
        help="Invert pan axis",
    )
    live_parser.add_argument(
        "--face-track-no-pan-inverted",
        dest="face_track_pan_inverted",
        action="store_false",
        help="Do not invert pan axis",
    )
    live_parser.add_argument(
        "--face-track-tilt-inverted",
        dest="face_track_tilt_inverted",
        action="store_true",
        help="Invert tilt axis",
    )
    live_parser.add_argument(
        "--face-track-no-tilt-inverted",
        dest="face_track_tilt_inverted",
        action="store_false",
        help="Do not invert tilt axis",
    )

    args = parser.parse_args()
    if args.command == "file-once":
        run_file_once(
            args.wav,
            use_mock_remote=not args.real_remote,
            mock_playback=not args.local_playback,
        )
    elif args.command == "live":
        run_live_loop_with_optional_face_tracking(args)


if __name__ == "__main__":
    main()
