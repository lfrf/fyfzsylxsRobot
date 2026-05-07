from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from typing import Any, Callable

from shared.logging_utils import log_event
from shared.schemas import FaceIdentitySchema, VisionContext

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class IdentityWatcherConfig:
    resolve_url: str | None = None
    session_id: str = "demo-session-001"
    poll_interval_s: float = 1.0
    context_seconds: float = 2.0
    resolve_timeout_s: float = 5.0
    persistable_sources: tuple[str, ...] = field(default_factory=lambda: ("insightface",))
    require_embedding_model: bool = True


@dataclass(frozen=True)
class IdentityWatcherResult:
    face_id: str
    user_id: str | None = None
    display_name: str | None = None
    persisted: bool = False
    identity_source: str | None = None
    error: str | None = None


IdentityResolvedCallback = Callable[[FaceIdentitySchema, IdentityWatcherResult], None]


class IdentityWatcher:
    """Background worker that silently binds real face identities during work mode."""

    def __init__(
        self,
        *,
        vision_provider: Any,
        config: IdentityWatcherConfig | None = None,
        on_identity_resolved: IdentityResolvedCallback | None = None,
    ) -> None:
        self.vision_provider = vision_provider
        self.config = config or IdentityWatcherConfig()
        self.on_identity_resolved = on_identity_resolved
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._provider_lock = threading.RLock()
        self._resolved_face_ids: set[str] = set()

    def start(self, *, shared_camera_mode: bool = False) -> None:
        if self._thread is not None and self._thread.is_alive():
            return

        self._resolved_face_ids.clear()
        self._stop_event.clear()
        self._restart_provider(shared_camera_mode=shared_camera_mode)
        self._thread = threading.Thread(
            target=self._run_loop,
            daemon=True,
            name="identity-watcher",
        )
        self._thread.start()
        log_event(
            "identity_watcher_started",
            shared_camera_mode=shared_camera_mode,
            poll_interval_s=self.config.poll_interval_s,
        )

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=3.0)
            self._thread = None
        self._stop_provider()
        self._resolved_face_ids.clear()
        log_event("identity_watcher_stopped")

    def switch_to_shared_camera(self) -> None:
        self._restart_provider(shared_camera_mode=True)
        log_event("identity_watcher_shared_camera_enabled")

    def switch_to_own_camera(self) -> None:
        self._restart_provider(shared_camera_mode=False)
        log_event("identity_watcher_own_camera_enabled")

    def probe_once(self) -> IdentityWatcherResult | None:
        context = self._get_context()
        if context is None:
            return None
        return self._handle_context(context)

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.probe_once()
            except Exception as exc:
                log_event("identity_watcher_probe_failed", error=str(exc), level="warning")
            self._stop_event.wait(max(0.2, self.config.poll_interval_s))

    def _handle_context(self, context: VisionContext) -> IdentityWatcherResult | None:
        face_identity = context.face_identity
        if not self._is_real_persistable_face(face_identity):
            return None

        assert face_identity is not None
        face_id = str(face_identity.face_id or "").strip()
        if face_id in self._resolved_face_ids:
            return None

        result = self._resolve_face(face_identity)
        self._resolved_face_ids.add(face_id)
        log_event(
            "identity_watcher_face_resolved",
            face_id=result.face_id,
            user_id=result.user_id,
            persisted=result.persisted,
            identity_source=result.identity_source,
            display_name=result.display_name,
            error=result.error,
        )
        if self.on_identity_resolved is not None:
            self.on_identity_resolved(face_identity, result)
        return result

    def _is_real_persistable_face(self, face_identity: FaceIdentitySchema | None) -> bool:
        if face_identity is None or not face_identity.face_detected:
            return False
        if not str(face_identity.face_id or "").strip():
            return False
        source = str(face_identity.source or "").strip().lower()
        allowed_sources = {item.strip().lower() for item in self.config.persistable_sources if item.strip()}
        if source not in allowed_sources:
            return False
        if self.config.require_embedding_model and not str(face_identity.embedding_model or "").strip():
            return False
        return True

    def _resolve_face(self, face_identity: FaceIdentitySchema) -> IdentityWatcherResult:
        face_id = str(face_identity.face_id or "").strip()
        if not self.config.resolve_url:
            return IdentityWatcherResult(face_id=face_id)

        try:
            import httpx  # type: ignore
        except Exception as exc:
            return IdentityWatcherResult(face_id=face_id, error=f"httpx_unavailable:{exc}")

        payload = {
            "session_id": self.config.session_id,
            "face_id": face_id,
            "source": "raspi_identity_watcher",
        }
        try:
            with httpx.Client(timeout=self.config.resolve_timeout_s) as client:
                response = client.post(self.config.resolve_url, json=payload)
            if response.status_code >= 400:
                return IdentityWatcherResult(
                    face_id=face_id,
                    error=f"resolve_status_{response.status_code}",
                )
            data = response.json()
        except Exception as exc:
            return IdentityWatcherResult(face_id=face_id, error=str(exc))

        identity = data.get("identity") if isinstance(data, dict) else {}
        identity = identity if isinstance(identity, dict) else {}
        return IdentityWatcherResult(
            face_id=str(identity.get("face_id") or face_id),
            user_id=identity.get("user_id"),
            display_name=identity.get("display_name"),
            persisted=bool(identity.get("persisted", False)),
            identity_source=identity.get("identity_source"),
        )

    def _get_context(self) -> VisionContext | None:
        with self._provider_lock:
            try:
                return self.vision_provider.get_context(seconds=self.config.context_seconds)
            except Exception as exc:
                logger.warning("identity_watcher_get_context_failed: %s", exc)
                return None

    def _restart_provider(self, *, shared_camera_mode: bool) -> None:
        with self._provider_lock:
            if hasattr(self.vision_provider, "stop"):
                self.vision_provider.stop()
            if hasattr(self.vision_provider, "set_shared_camera_mode"):
                self.vision_provider.set_shared_camera_mode(shared_camera_mode)
            if hasattr(self.vision_provider, "start"):
                self.vision_provider.start()

    def _stop_provider(self) -> None:
        with self._provider_lock:
            if hasattr(self.vision_provider, "stop"):
                self.vision_provider.stop()
