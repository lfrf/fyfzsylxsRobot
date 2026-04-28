from __future__ import annotations

import json
import logging
import os
import sys
from collections.abc import Mapping
from typing import Any


LOGGER_NAME = "robotmatch"
_CONFIGURED = False


def get_robot_logger() -> logging.Logger:
    global _CONFIGURED
    logger = logging.getLogger(LOGGER_NAME)
    if not _CONFIGURED:
        level_name = os.getenv("ROBOT_LOG_LEVEL", "INFO").strip().upper() or "INFO"
        level = getattr(logging, level_name, logging.INFO)
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        logger.handlers.clear()
        logger.addHandler(handler)
        logger.setLevel(level)
        logger.propagate = False
        _CONFIGURED = True
    return logger


def log_event(event: str, *, level: str = "info", **fields: Any) -> None:
    logger = get_robot_logger()
    sanitized = sanitize_log_fields(fields)
    if _env_bool("ROBOT_LOG_JSON", default=False):
        message = json.dumps({"event": event, **sanitized}, ensure_ascii=False, default=str)
    else:
        payload = " ".join(f"{key}={_format_value(value)}" for key, value in sanitized.items())
        message = f"event={event}" + (f" {payload}" if payload else "")

    log_method = getattr(logger, level.lower(), logger.info)
    log_method(message)


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


def _format_value(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, default=str)
    return str(value)


def _env_bool(name: str, *, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


__all__ = ["get_robot_logger", "is_debug_trace_enabled", "log_event", "sanitize_log_fields"]
