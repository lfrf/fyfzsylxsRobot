import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    edge_backend_base: str
    chat_timeout_seconds: float
    log_dir: str
    eyes_mode: str
    servo_mode: str
    audio_mode: str
    servo_pan_channel: int
    servo_tilt_channel: int
    servo_min_degree: int
    servo_max_degree: int


def _read_int(name: str, default: int) -> int:
    value = os.getenv(name, str(default)).strip()
    try:
        return int(value)
    except ValueError:
        return default


def _read_float(name: str, default: float) -> float:
    value = os.getenv(name, str(default)).strip()
    try:
        return float(value)
    except ValueError:
        return default


def load_settings() -> Settings:
    min_degree = _read_int("ROBOT_SERVO_MIN_DEGREE", 70)
    max_degree = _read_int("ROBOT_SERVO_MAX_DEGREE", 110)
    if min_degree > max_degree:
        min_degree, max_degree = max_degree, min_degree

    return Settings(
        edge_backend_base=os.getenv("EDGE_BACKEND_BASE", "http://127.0.0.1:8000").rstrip("/"),
        chat_timeout_seconds=_read_float("ROBOT_CHAT_TIMEOUT_SECONDS", 20.0),
        log_dir=os.getenv("LOG_DIR", "/logs/robot-runtime"),
        eyes_mode=os.getenv("ROBOT_EYES_MODE", "mock").strip().lower() or "mock",
        servo_mode=os.getenv("ROBOT_SERVO_MODE", "mock").strip().lower() or "mock",
        audio_mode=os.getenv("ROBOT_AUDIO_MODE", "mock").strip().lower() or "mock",
        servo_pan_channel=_read_int("ROBOT_SERVO_PAN_CHANNEL", 0),
        servo_tilt_channel=_read_int("ROBOT_SERVO_TILT_CHANNEL", 1),
        servo_min_degree=min_degree,
        servo_max_degree=max_degree,
    )
