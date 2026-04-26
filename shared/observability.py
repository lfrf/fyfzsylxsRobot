import json
import uuid
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any
from zoneinfo import ZoneInfo

LOG_TIMEZONE = ZoneInfo("Asia/Shanghai")


def build_run_id(service_name: str) -> str:
    timestamp = datetime.now(LOG_TIMEZONE).strftime("%Y%m%dT%H%M%S")
    return f"{service_name}-{timestamp}-CN08-{uuid.uuid4().hex[:8]}"


def sanitize_payload(value: Any, *, max_text_length: int = 2000) -> Any:
    if hasattr(value, "model_dump"):
        value = value.model_dump()
    elif hasattr(value, "dict"):
        value = value.dict()

    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            if key.endswith("_base64") and isinstance(item, str):
                sanitized[key] = f"<redacted:{len(item)} chars>"
                continue
            sanitized[key] = sanitize_payload(item, max_text_length=max_text_length)
        return sanitized

    if isinstance(value, list):
        return [sanitize_payload(item, max_text_length=max_text_length) for item in value]

    if isinstance(value, str) and len(value) > max_text_length:
        return f"{value[:max_text_length]}...<truncated:{len(value) - max_text_length} chars>"

    return value


def _format_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def flatten_mapping(prefix: str, value: Any) -> list[tuple[str, str]]:
    if isinstance(value, dict):
        flattened: list[tuple[str, str]] = []
        for key, item in value.items():
            next_prefix = f"{prefix}.{key}" if prefix else key
            flattened.extend(flatten_mapping(next_prefix, item))
        return flattened

    if isinstance(value, list):
        flattened = []
        for index, item in enumerate(value):
            next_prefix = f"{prefix}[{index}]"
            flattened.extend(flatten_mapping(next_prefix, item))
        if not value:
            return [(prefix, "[]")]
        return flattened

    return [(prefix, _format_scalar(value))]


class JsonlRunLogger:
    def __init__(
        self,
        *,
        service_name: str,
        log_dir: str,
        channel: str,
        run_id: str,
    ) -> None:
        self.service_name = service_name
        self.channel = channel
        self.run_id = run_id
        self.log_dir = Path(log_dir).expanduser()
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.file_path = self.log_dir / f"{service_name}-{channel}-{run_id}.jsonl"
        self.pretty_file_path = self.log_dir / f"{service_name}-{channel}-{run_id}.log"
        self._lock = Lock()

    def emit(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        record = {
            "ts": datetime.now(LOG_TIMEZONE).isoformat(timespec="milliseconds"),
            "service": self.service_name,
            "channel": self.channel,
            "run_id": self.run_id,
            "event_type": event_type,
            "payload": sanitize_payload(payload),
        }

        with self._lock:
            with self.file_path.open("a", encoding="utf-8") as output_file:
                output_file.write(json.dumps(record, ensure_ascii=False, default=str))
                output_file.write("\n")
            with self.pretty_file_path.open("a", encoding="utf-8") as output_file:
                output_file.write(self._render_pretty_record(record))
                output_file.write("\n")

        return record

    def _render_pretty_record(self, record: dict[str, Any]) -> str:
        lines = [
            "-" * 80,
            f"ts: {record['ts']}",
            f"service: {record['service']}",
            f"channel: {record['channel']}",
            f"run_id: {record['run_id']}",
            f"event_type: {record['event_type']}",
        ]
        for key, value in flatten_mapping("payload", record.get("payload", {})):
            lines.append(f"{key}: {value}")
        return "\n".join(lines)
