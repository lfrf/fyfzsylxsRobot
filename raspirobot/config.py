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
    )
