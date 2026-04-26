import sys
import time
from pathlib import Path

SHARED_PATH_CANDIDATES = [
    Path("/shared"),
    Path(__file__).resolve().parents[3] / "shared" if len(Path(__file__).resolve().parents) > 3 else None,
]

for candidate in SHARED_PATH_CANDIDATES:
    if candidate and candidate.exists() and str(candidate) not in sys.path:
        sys.path.append(str(candidate))

from observability import JsonlRunLogger, build_run_id  # noqa: E402

from config import settings


class EdgeObservability:
    def __init__(self) -> None:
        self.service_name = "edge-backend"
        self.run_id = build_run_id(self.service_name)
        self.started_at = time.perf_counter()
        self._events_logger = JsonlRunLogger(
            service_name=self.service_name,
            log_dir=settings.log_dir,
            channel="events",
            run_id=self.run_id,
        )
        self._bridge_logger = JsonlRunLogger(
            service_name=self.service_name,
            log_dir=settings.log_dir,
            channel="bridge",
            run_id=self.run_id,
        )

    def log_run_start(self) -> None:
        self._events_logger.emit(
            "run_start",
            {
                "cloud_api_base": settings.cloud_api_base,
                "cloud_ws_chat_endpoint": settings.cloud_ws_chat_endpoint,
                "remote_transport": settings.remote_transport,
                "request_timeout_seconds": settings.request_timeout_seconds,
                "audio_pipeline_role": settings.audio_pipeline_role,
                "local_video_frame_limit": settings.local_video_frame_limit,
                "local_video_max_dimension": settings.local_video_max_dimension,
                "log_dir": settings.log_dir,
            },
        )

    def log_run_stop(self) -> None:
        self._events_logger.emit(
            "run_stop",
            {
                "uptime_seconds": round(time.perf_counter() - self.started_at, 3),
            },
        )

    def log_chat_request_received(self, request_id: str, payload: dict) -> None:
        self._events_logger.emit(
            "chat_request_received",
            {
                "request_id": request_id,
                **payload,
            },
        )

    def log_chat_request_prepared(self, request_id: str, payload: dict) -> None:
        self._events_logger.emit(
            "chat_request_prepared",
            {
                "request_id": request_id,
                **payload,
            },
        )

    def log_bridge_outbound(self, request_id: str, url: str, payload: dict) -> None:
        self._bridge_logger.emit(
            "bridge_outbound",
            {
                "request_id": request_id,
                "url": url,
                "payload": payload,
            },
        )

    def log_bridge_inbound(self, request_id: str, status_code: int, latency_ms: int, payload: dict) -> None:
        self._bridge_logger.emit(
            "bridge_inbound",
            {
                "request_id": request_id,
                "status_code": status_code,
                "latency_ms": latency_ms,
                "payload": payload,
            },
        )

    def log_bridge_error(self, request_id: str, latency_ms: int, detail: str, status_code: int, payload: dict) -> None:
        self._bridge_logger.emit(
            "bridge_error",
            {
                "request_id": request_id,
                "status_code": status_code,
                "latency_ms": latency_ms,
                "detail": detail,
                "payload": payload,
            },
        )

    def log_chat_response(self, request_id: str, latency_ms: int, payload: dict) -> None:
        self._events_logger.emit(
            "chat_response",
            {
                "request_id": request_id,
                "latency_ms": latency_ms,
                **payload,
            },
        )

    def log_chat_error(self, request_id: str, latency_ms: int, detail: str, status_code: int) -> None:
        self._events_logger.emit(
            "chat_error",
            {
                "request_id": request_id,
                "latency_ms": latency_ms,
                "detail": detail,
                "status_code": status_code,
            },
        )


edge_observability = EdgeObservability()
