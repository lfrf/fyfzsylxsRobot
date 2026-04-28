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


def load_settings() -> Settings:
    return Settings(
        remote_base_url=os.getenv("ROBOT_REMOTE_BASE_URL", "http://127.0.0.1:19000").rstrip("/"),
        chat_endpoint=os.getenv("ROBOT_CHAT_ENDPOINT", "/v1/robot/chat_turn"),
        session_id=os.getenv("ROBOT_SESSION_ID", "demo-session-001"),
        default_mode=os.getenv("ROBOT_MODE_DEFAULT", os.getenv("ROBOT_DEFAULT_MODE", "elderly")),
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
    )


def _none_if_empty(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if not value or value.lower() in {"none", "null", "off"}:
        return None
    return value
