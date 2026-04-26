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


class OrchestratorObservability:
    def __init__(self) -> None:
        self.service_name = "orchestrator"
        self.run_id = build_run_id(self.service_name)
        self.started_at = time.perf_counter()
        self._events_logger = JsonlRunLogger(
            service_name=self.service_name,
            log_dir=settings.log_dir,
            channel="events",
            run_id=self.run_id,
        )

    def log_run_start(self) -> None:
        self._events_logger.emit(
            "run_start",
            {
                "llm_provider": settings.llm_provider,
                "llm_model": settings.llm_model,
                "speech_service_enabled": settings.speech_service_enabled,
                "speech_service_base": settings.speech_service_base,
                "vision_service_enabled": settings.vision_service_enabled,
                "vision_service_base": settings.vision_service_base,
                "emotion_service_enabled": settings.emotion_service_enabled,
                "emotion_service_base": settings.emotion_service_base,
                "rag_enabled": settings.rag_enabled,
                "rag_kb_dir": settings.rag_kb_dir,
                "rag_processed_dir": settings.rag_processed_dir,
                "rag_index_dir": settings.rag_index_dir,
                "rag_top_k": settings.rag_top_k,
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

    def log_chat_request_received(self, session_id: str, turn_id: int, payload: dict) -> None:
        self._events_logger.emit(
            "chat_request_received",
            {
                "request_key": f"{session_id}:{turn_id}",
                **payload,
            },
        )

    def log_alignment_ready(self, session_id: str, turn_id: int, payload: dict) -> None:
        self._events_logger.emit(
            "alignment_ready",
            {
                "request_key": f"{session_id}:{turn_id}",
                **payload,
            },
        )

    def log_chat_response(self, session_id: str, turn_id: int, latency_ms: int, payload: dict) -> None:
        self._events_logger.emit(
            "chat_response",
            {
                "request_key": f"{session_id}:{turn_id}",
                "latency_ms": latency_ms,
                **payload,
            },
        )


orchestrator_observability = OrchestratorObservability()
