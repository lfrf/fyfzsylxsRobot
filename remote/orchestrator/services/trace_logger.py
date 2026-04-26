import sys
from pathlib import Path

SHARED_PATH_CANDIDATES = [
    Path("/shared"),
    Path(__file__).resolve().parents[3] / "shared" if len(Path(__file__).resolve().parents) > 3 else None,
]

for candidate in SHARED_PATH_CANDIDATES:
    if candidate and candidate.exists() and str(candidate) not in sys.path:
        sys.path.append(str(candidate))

from trace_store import TraceStore  # noqa: E402

from config import settings


class OrchestratorTraceLogger:
    def __init__(self) -> None:
        self._store = TraceStore(service_name="orchestrator", root_dir=settings.trace_root_dir)

    def log_event(
        self,
        *,
        trace_id: str | None,
        session_id: str,
        turn_id: int,
        event_type: str,
        payload_summary: dict,
        latency_ms: int | None = None,
    ) -> str:
        return self._store.emit(
            trace_id=trace_id,
            session_id=session_id,
            turn_id=turn_id,
            event_type=event_type,
            payload_summary=payload_summary,
            latency_ms=latency_ms,
        )

    def write_summary(self, *, trace_id: str | None, session_id: str, turn_id: int, payload: dict) -> str:
        return self._store.write_summary(
            trace_id=trace_id,
            session_id=session_id,
            turn_id=turn_id,
            payload=payload,
        )


orchestrator_trace_logger = OrchestratorTraceLogger()
