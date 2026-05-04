import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    remote_base_url: str
    chat_endpoint: str
    session_id: str
    default_mode: str
    request_timeout_seconds: float
    mock_audio_base64: str
    audio_capture_provider: str
    audio_output_provider: str
    audio_capture_device: str | None
    audio_playback_device: str | None
    audio_capture_command: str
    audio_playback_command: str
    audio_sample_rate: int
    audio_channels: int
    audio_sample_width: int
    audio_frame_ms: int
    vad_rms_threshold: float
    vad_speech_start_frames: int
    vad_silence_timeout_ms: int
    vad_max_utterance_seconds: float
    vad_pre_roll_ms: int
    audio_work_dir: str
    live_loop_sleep_seconds: float
    # Audio preprocessing fields (disabled by default for backward compatibility)
    audio_preprocess_enabled: bool
    audio_enable_noise_gate: bool
    audio_enable_trim: bool
    audio_min_speech_ms: int
    audio_post_speech_padding_ms: int
    audio_noise_calibration_ms: int
    audio_noise_gate_ratio: float
    audio_min_rms: float
    audio_save_debug_wav: bool
    # Post-playback cooldown configuration
    audio_post_playback_cooldown_ms: int
    # Invalid utterance drop configuration
    audio_drop_invalid_utterance: bool
    audio_drop_reasons: str
    eyes_provider: str
    eyes_assets_dir: str
    eyes_frame_fps: int
    eyes_screen_width: int
    eyes_screen_height: int
    eyes_rotation: int
    eyes_spi_port: int
    eyes_spi_speed_hz: int
    eyes_dc_gpio: int
    eyes_rst_gpio: int
    eyes_left_cs: int
    eyes_right_cs: int
    eyes_right_enabled: bool
    eyes_mirror_right: bool
    eyes_gpio_chip: str
    eyes_left_dc_gpio: int
    eyes_right_dc_gpio: int
    eyes_left_assets_dir: str
    eyes_right_assets_dir: str
    eyes_right_spi_port: int
    eyes_left_rotation: int
    eyes_right_rotation: int
    eyes_left_phase_offset_ms: int
    eyes_right_phase_offset_ms: int


def load_settings() -> Settings:
    return Settings(
        remote_base_url=os.getenv("ROBOT_REMOTE_BASE_URL", "http://127.0.0.1:19000").rstrip("/"),
        chat_endpoint=os.getenv("ROBOT_CHAT_ENDPOINT", "/v1/robot/chat_turn"),
        session_id=os.getenv("ROBOT_SESSION_ID", "demo-session-001"),
        default_mode=os.getenv("ROBOT_MODE_DEFAULT", os.getenv("ROBOT_DEFAULT_MODE", "care")),
        request_timeout_seconds=float(
            os.getenv("ROBOT_REMOTE_TIMEOUT_SECONDS", os.getenv("ROBOT_REQUEST_TIMEOUT_SECONDS", "40"))
        ),
        mock_audio_base64=os.getenv("ROBOT_MOCK_AUDIO_BASE64", "UklGRiQAAABXQVZFZm10IBAAAAABAAEA"),
        audio_capture_provider=os.getenv("ROBOT_AUDIO_CAPTURE_PROVIDER", "local_command").strip().lower(),
        audio_output_provider=os.getenv("ROBOT_AUDIO_OUTPUT_PROVIDER", "local_command").strip().lower(),
        audio_capture_device=_none_if_empty(os.getenv("ROBOT_AUDIO_CAPTURE_DEVICE", "default")),
        audio_playback_device=_none_if_empty(os.getenv("ROBOT_AUDIO_PLAYBACK_DEVICE", "default")),
        audio_capture_command=os.getenv("ROBOT_AUDIO_CAPTURE_COMMAND", "arecord").strip() or "arecord",
        audio_playback_command=os.getenv("ROBOT_AUDIO_PLAYBACK_COMMAND", "aplay").strip() or "aplay",
        audio_sample_rate=int(os.getenv("ROBOT_AUDIO_SAMPLE_RATE", "16000")),
        audio_channels=int(os.getenv("ROBOT_AUDIO_CHANNELS", "1")),
        audio_sample_width=int(os.getenv("ROBOT_AUDIO_SAMPLE_WIDTH", "2")),
        audio_frame_ms=int(os.getenv("ROBOT_AUDIO_FRAME_MS", "30")),
        vad_rms_threshold=float(os.getenv("ROBOT_VAD_RMS_THRESHOLD", "500")),
        vad_speech_start_frames=int(os.getenv("ROBOT_VAD_SPEECH_START_FRAMES", "3")),
        vad_silence_timeout_ms=int(os.getenv("ROBOT_VAD_SILENCE_TIMEOUT_MS", "900")),
        vad_max_utterance_seconds=float(os.getenv("ROBOT_VAD_MAX_UTTERANCE_SECONDS", "15")),
        vad_pre_roll_ms=int(os.getenv("ROBOT_VAD_PRE_ROLL_MS", "300")),
        audio_work_dir=os.getenv("ROBOT_AUDIO_WORK_DIR", "/tmp/raspirobot_audio").strip() or "/tmp/raspirobot_audio",
        live_loop_sleep_seconds=float(os.getenv("ROBOT_LIVE_LOOP_SLEEP_SECONDS", "0.05")),
        # Audio preprocessing - disabled by default for backward compatibility
        audio_preprocess_enabled=_bool_env("ROBOT_AUDIO_PREPROCESS_ENABLED", default=False),
        audio_enable_noise_gate=_bool_env("ROBOT_AUDIO_ENABLE_NOISE_GATE", default=True),
        audio_enable_trim=_bool_env("ROBOT_AUDIO_ENABLE_TRIM", default=True),
        audio_min_speech_ms=int(os.getenv("ROBOT_AUDIO_MIN_SPEECH_MS", "400")),
        audio_post_speech_padding_ms=int(os.getenv("ROBOT_AUDIO_POST_SPEECH_PADDING_MS", "150")),
        audio_noise_calibration_ms=int(os.getenv("ROBOT_AUDIO_NOISE_CALIBRATION_MS", "1000")),
        audio_noise_gate_ratio=float(os.getenv("ROBOT_AUDIO_NOISE_GATE_RATIO", "3.0")),
        audio_min_rms=float(os.getenv("ROBOT_AUDIO_MIN_RMS", "80")),
        audio_save_debug_wav=_bool_env("ROBOT_AUDIO_SAVE_DEBUG_WAV", default=False),
        audio_post_playback_cooldown_ms=int(os.getenv("ROBOT_AUDIO_POST_PLAYBACK_COOLDOWN_MS", "0")),
        audio_drop_invalid_utterance=_bool_env("ROBOT_AUDIO_DROP_INVALID_UTTERANCE", default=False),
        audio_drop_reasons=os.getenv("ROBOT_AUDIO_DROP_REASONS", "no_speech_detected,speech_too_short").strip(),
        eyes_provider=os.getenv("ROBOT_EYES_PROVIDER", "mock").strip().lower() or "mock",
        eyes_assets_dir=os.getenv("ROBOT_EYES_ASSETS_DIR", "/tmp/raspirobot_eyes").strip() or "/tmp/raspirobot_eyes",
        eyes_frame_fps=int(os.getenv("ROBOT_EYES_FRAME_FPS", "8")),
        eyes_screen_width=int(os.getenv("ROBOT_EYES_SCREEN_WIDTH", "240")),
        eyes_screen_height=int(os.getenv("ROBOT_EYES_SCREEN_HEIGHT", "320")),
        eyes_rotation=int(os.getenv("ROBOT_EYES_ROTATION", "0")),
        eyes_spi_port=int(os.getenv("ROBOT_EYES_SPI_PORT", "0")),
        eyes_spi_speed_hz=int(os.getenv("ROBOT_EYES_SPI_SPEED_HZ", "24000000")),
        eyes_dc_gpio=int(os.getenv("ROBOT_EYES_DC_GPIO", "25")),
        eyes_rst_gpio=int(os.getenv("ROBOT_EYES_RST_GPIO", "24")),
        eyes_left_cs=int(os.getenv("ROBOT_EYES_LEFT_CS", "0")),
        eyes_right_cs=int(os.getenv("ROBOT_EYES_RIGHT_CS", "1")),
        eyes_right_enabled=_bool_env("ROBOT_EYES_RIGHT_ENABLED", default=True),
        eyes_mirror_right=_bool_env("ROBOT_EYES_MIRROR_RIGHT", default=False),
        eyes_gpio_chip=os.getenv("ROBOT_EYES_GPIO_CHIP", "/dev/gpiochip0").strip() or "/dev/gpiochip0",
        eyes_left_dc_gpio=int(os.getenv("ROBOT_EYES_LEFT_DC_GPIO", "25")),
        eyes_right_dc_gpio=int(os.getenv("ROBOT_EYES_RIGHT_DC_GPIO", "24")),
        eyes_left_assets_dir=os.getenv("ROBOT_EYES_LEFT_ASSETS_DIR", "").strip(),
        eyes_right_assets_dir=os.getenv("ROBOT_EYES_RIGHT_ASSETS_DIR", "").strip(),
        eyes_right_spi_port=int(os.getenv("ROBOT_EYES_RIGHT_SPI_PORT", "1")),
        eyes_left_rotation=int(os.getenv("ROBOT_EYES_LEFT_ROTATION", "270")),
        eyes_right_rotation=int(os.getenv("ROBOT_EYES_RIGHT_ROTATION", "90")),
        eyes_left_phase_offset_ms=int(os.getenv("ROBOT_EYES_LEFT_PHASE_OFFSET_MS", "0")),
        eyes_right_phase_offset_ms=int(os.getenv("ROBOT_EYES_RIGHT_PHASE_OFFSET_MS", "0")),
    )


def _none_if_empty(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if not value or value.lower() in {"none", "null", "off"}:
        return None
    return value


def _bool_env(name: str, *, default: bool) -> bool:
    """Read an environment variable as a boolean.

    Accepted truthy values  : 1, true, yes, on
    Accepted falsy values   : 0, false, no, off
    Missing or empty value  : returns *default*
    Unrecognised value      : logs a warning and returns *default*
    """
    raw = os.getenv(name)
    if raw is None:
        return default
    normalised = raw.strip().lower()
    if normalised in {"1", "true", "yes", "on"}:
        return True
    if normalised in {"0", "false", "no", "off"}:
        return False
    # Unrecognised value - fall back to default rather than crashing live loop
    import sys

    print(
        f"[config] WARNING: unrecognised boolean value for {name}={raw!r}; "
        f"using default={default}",
        file=sys.stderr,
    )
    return default
