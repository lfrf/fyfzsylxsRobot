from __future__ import annotations

import json
import logging
import os
import sys
from collections.abc import Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator
from uuid import uuid4
from zoneinfo import ZoneInfo


LOGGER_NAME = "robotmatch"
LOG_TIMEZONE = "Asia/Shanghai"
_CONFIGURED = False
_LOG_SESSION_ID: str | None = None
_LOG_FILE_PATH: Path | None = None
_LOG_CONTEXT: ContextVar[dict[str, Any]] = ContextVar("robotmatch_log_context", default={})


def get_robot_logger() -> logging.Logger:
    global _CONFIGURED, _LOG_FILE_PATH
    logger = logging.getLogger(LOGGER_NAME)
    if not _CONFIGURED:
        level_name = os.getenv("ROBOT_LOG_LEVEL", "INFO").strip().upper() or "INFO"
        level = getattr(logging, level_name, logging.INFO)
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        _clear_handlers(logger)
        logger.addHandler(handler)
        log_dir = _get_log_session_dir()
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            _LOG_FILE_PATH = log_dir / "robotmatch.log"
            file_handler = logging.FileHandler(_LOG_FILE_PATH, encoding="utf-8")
            file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
            logger.addHandler(file_handler)
        except OSError as exc:
            print(f"robotmatch logging file setup failed: {exc}", file=sys.stderr)
        logger.setLevel(level)
        logger.propagate = False
        _CONFIGURED = True
    return logger


def log_event(event: str, *, level: str = "info", **fields: Any) -> None:
    logger = get_robot_logger()
    active_fields = {**_LOG_CONTEXT.get(), **fields}
    event_session_id = _safe_path_token(str(active_fields.get("log_session_id") or get_log_session_id()))
    sanitized = {**sanitize_log_fields(active_fields), "log_session_id": event_session_id}
    if _env_bool("ROBOT_LOG_JSON", default=False):
        message = json.dumps({"event": event, **sanitized}, ensure_ascii=False, default=str)
    else:
        payload = " ".join(f"{key}={_format_value(value)}" for key, value in sanitized.items())
        message = f"event={event}" + (f" {payload}" if payload else "")

    log_method = getattr(logger, level.lower(), logger.info)
    log_method(message)
    if event_session_id != get_log_session_id():
        _write_dynamic_session_log(event_session_id, level.upper(), message)


def sanitize_log_fields(value: Any) -> Any:
    if isinstance(value, Mapping):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if key_text == "audio_base64":
                sanitized["audio_base64_len"] = len(item or "")
                continue
            sanitized[key_text] = sanitize_log_fields(item)
        return sanitized
    if isinstance(value, list):
        return [sanitize_log_fields(item) for item in value]
    return value


def is_debug_trace_enabled() -> bool:
    return _env_bool("ROBOT_DEBUG_TRACE", default=False)


def get_log_session_id() -> str:
    global _LOG_SESSION_ID
    if _LOG_SESSION_ID is None:
        env_session_id = os.getenv("ROBOT_LOG_SESSION_ID", "").strip()
        if env_session_id:
            _LOG_SESSION_ID = _safe_path_token(env_session_id)
        else:
            timestamp = _now_china().strftime("%Y%m%d-%H%M%S")
            _LOG_SESSION_ID = f"cn-{timestamp}-{uuid4().hex[:8]}"
    return _LOG_SESSION_ID


def get_active_log_session_id() -> str:
    context_session_id = _LOG_CONTEXT.get().get("log_session_id")
    if context_session_id:
        return _safe_path_token(str(context_session_id))
    return get_log_session_id()


def get_log_file_path() -> str | None:
    return None if _LOG_FILE_PATH is None else str(_LOG_FILE_PATH)


def get_log_session_dir(log_session_id: str | None = None) -> str:
    return str(_get_log_session_dir(_safe_path_token(log_session_id) if log_session_id else None))


def start_log_session(session_id: str | None = None) -> str:
    global _CONFIGURED, _LOG_FILE_PATH, _LOG_SESSION_ID
    if session_id:
        _LOG_SESSION_ID = _safe_path_token(session_id)
    elif os.getenv("ROBOT_LOG_SESSION_ID", "").strip():
        _LOG_SESSION_ID = _safe_path_token(os.getenv("ROBOT_LOG_SESSION_ID", "").strip())
    else:
        timestamp = _now_china().strftime("%Y%m%d-%H%M%S")
        _LOG_SESSION_ID = f"cn-{timestamp}-{uuid4().hex[:8]}"

    logger = logging.getLogger(LOGGER_NAME)
    if _CONFIGURED:
        _clear_handlers(logger)
        _CONFIGURED = False
        _LOG_FILE_PATH = None
    get_robot_logger()
    return _LOG_SESSION_ID


@contextmanager
def log_context(**fields: Any) -> Iterator[None]:
    current = dict(_LOG_CONTEXT.get())
    current.update({key: value for key, value in fields.items() if value is not None})
    token = _LOG_CONTEXT.set(current)
    try:
        yield
    finally:
        _LOG_CONTEXT.reset(token)


def _format_value(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, default=str)
    return str(value)


def _env_bool(name: str, *, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _get_log_session_dir(log_session_id: str | None = None) -> Path:
    log_root = os.getenv("ROBOT_LOG_DIR", "").strip()
    if log_root:
        root = Path(log_root)
    else:
        root = Path(__file__).resolve().parents[1] / "logs"
    return root / (log_session_id or get_log_session_id())


def _write_dynamic_session_log(log_session_id: str, level_name: str, message: str) -> None:
    try:
        log_dir = _get_log_session_dir(log_session_id)
        log_dir.mkdir(parents=True, exist_ok=True)
        timestamp = _now_china().strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
        with (log_dir / "robotmatch.log").open("a", encoding="utf-8") as handle:
            handle.write(f"{timestamp} {level_name} {LOGGER_NAME} {message}\n")
    except OSError as exc:
        print(f"robotmatch dynamic log write failed: {exc}", file=sys.stderr)


def _clear_handlers(logger: logging.Logger) -> None:
    for handler in logger.handlers:
        handler.close()
    logger.handlers.clear()


def _safe_path_token(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in value)
    return cleaned.strip("-_") or f"session-{uuid4().hex[:8]}"


def _now_china() -> datetime:
    try:
        return datetime.now(ZoneInfo(LOG_TIMEZONE))
    except Exception:
        return datetime.now(timezone(timedelta(hours=8)))


__all__ = [
    "get_active_log_session_id",
    "get_log_file_path",
    "get_log_session_dir",
    "get_log_session_id",
    "get_robot_logger",
    "is_debug_trace_enabled",
    "log_context",
    "log_event",
    "sanitize_log_fields",
    "start_log_session",
]
