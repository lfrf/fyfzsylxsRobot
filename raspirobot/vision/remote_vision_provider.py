"""
RemoteVisionContextProvider

后台线程持续从摄像头采帧并上传到 video-cache-service，
每次 get_context() 时调用 vision-service /from-cache 拿人脸识别结果，
填入 VisionContext.face_identity。

支持两种模式：
1. 独立摄像头模式（默认）：自己开摄像头后台采帧
2. 帧注入模式：由外部（如人脸追踪线程）调用 inject_frame() 共享帧，
   避免摄像头被两个模块同时打开。
"""
from __future__ import annotations

import base64
import logging
import threading
import time
from dataclasses import dataclass
from typing import Any

from shared.contracts.schemas import FaceBoxSchema, FaceIdentitySchema, FaceObservationSchema, VisionContext
from shared.logging_utils import log_event

logger = logging.getLogger(__name__)


@dataclass
class RemoteVisionConfig:
    # video-cache-service 上传地址（树莓派本地隧道端口）
    ingest_url: str = "http://127.0.0.1:29001/v1/video/ingest"
    # vision-service from-cache 地址（服务器端，通过隧道或直连）
    from_cache_url: str = "http://127.0.0.1:29002/v1/vision/identity/from-cache"
    session_id: str = "robot-session-001"
    stream_id: str = "video-main"
    # 摄像头参数（仅独立摄像头模式使用）
    camera_width: int = 320
    camera_height: int = 240
    use_picamera2: bool = True
    cv2_device_index: int = 0
    hflip: bool = False
    vflip: bool = True
    # 上传频率：每 N 帧上传一次
    upload_every_n_frames: int = 3
    # 后台线程采帧间隔（秒，仅独立摄像头模式使用）
    capture_interval_s: float = 0.2
    # HTTP 超时
    upload_timeout_s: float = 5.0
    from_cache_timeout_s: float = 30.0
    query_mode: str = "latest"
    latest_window_ms: int = 6000
    latest_max_frames: int = 10
    prepare_max_frame_age_ms: int = 3000
    prepare_min_frames: int = 2


class RemoteVisionContextProvider:
    """
    实现 VisionContextProvider 协议。

    后台线程持续采帧上传，get_context() 时触发 from-cache 识别。
    """

    def __init__(self, config: RemoteVisionConfig | None = None) -> None:
        self.config = config or RemoteVisionConfig()
        self._frame_count = 0
        self._turn_id_counter = 0
        self._lock = threading.Lock()
        self._running = False
        self._thread: threading.Thread | None = None
        self._camera = None
        self._http_client = None
        self._last_face_identity: FaceIdentitySchema | None = None
        self._fresh_epoch_started_ms: int | None = None
        # 帧注入模式：外部注入的最新帧
        self._injected_frame: Any = None
        self._injected_frame_lock = threading.Lock()
        self._shared_camera_mode = False  # True = 帧注入模式，不自己开摄像头

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------

    def start(self) -> None:
        """启动后台上传线程。
        
        如果已通过 set_shared_camera_mode(True) 启用帧注入模式，
        则不开摄像头，只启动上传线程消费注入的帧。
        """
        if self._running:
            return
        try:
            self._init_http()
            if not self._shared_camera_mode:
                self._init_camera()
        except Exception as exc:
            logger.warning("remote_vision_provider_start_failed: %s", exc)
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._capture_loop if not self._shared_camera_mode else self._inject_loop,
            daemon=True,
            name="remote-vision-capture",
        )
        self._thread.start()
        logger.info(
            "remote_vision_provider_started mode=%s ingest_url=%s",
            "shared_camera" if self._shared_camera_mode else "own_camera",
            self.config.ingest_url,
        )

    def set_shared_camera_mode(self, enabled: bool) -> None:
        """启用帧注入模式，由外部调用 inject_frame() 提供帧，不自己开摄像头。"""
        self._shared_camera_mode = enabled

    def inject_frame(self, frame: Any) -> None:
        """由人脸追踪线程调用，把当前帧共享给视频上传逻辑。"""
        with self._injected_frame_lock:
            self._injected_frame = frame

    def begin_fresh_epoch(self, *, reason: str = "prepare") -> int:
        """Start a new visual epoch and discard any frame from the previous wake cycle."""
        epoch_ms = int(time.time() * 1000)
        with self._lock:
            self._fresh_epoch_started_ms = epoch_ms
            self._last_face_identity = None
        with self._injected_frame_lock:
            self._injected_frame = None
        log_event(
            "remote_vision_fresh_epoch_started",
            reason=reason,
            min_timestamp_ms=epoch_ms,
        )
        return epoch_ms

    def reset(self, *, reason: str = "reset") -> None:
        """Clear cached visual state so standby cannot leak an old face into the next wake."""
        with self._lock:
            self._fresh_epoch_started_ms = None
            self._last_face_identity = None
        with self._injected_frame_lock:
            self._injected_frame = None
        log_event("remote_vision_provider_reset", reason=reason)

    def stop(self) -> None:
        self._running = False
        self.reset(reason="stop")
        if self._thread is not None:
            self._thread.join(timeout=3.0)
        if self._camera is not None:
            try:
                self._camera.stop()
            except Exception:
                pass
        if self._http_client is not None:
            try:
                self._http_client.close()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # VisionContextProvider 协议
    # ------------------------------------------------------------------

    def get_context(self, seconds: float = 5.0) -> VisionContext:
        """
        每次 TurnManager 构建 payload 时调用。
        用当前 turn_id 向 vision-service 请求 from-cache 识别结果。
        """
        with self._lock:
            turn_id = f"turn-{self._turn_id_counter:04d}"
            self._turn_id_counter += 1

        face_identity = self._fetch_face_identity(turn_id, require_fresh=False)
        with self._lock:
            self._last_face_identity = face_identity

        return VisionContext(
            source="remote_vision_cache",
            latest=None,
            recent=[],
            image_frames=[],
            face_identity=face_identity,
            face_observations=[],
        )

    def get_prepare_context(self) -> VisionContext:
        """Fetch identity for PREPARING; stale or insufficient frames are rejected."""
        with self._lock:
            turn_id = f"turn-{self._turn_id_counter:04d}"
            self._turn_id_counter += 1

        face_identity = self._fetch_face_identity(turn_id, require_fresh=True)
        with self._lock:
            self._last_face_identity = face_identity

        return VisionContext(
            source="remote_vision_cache",
            latest=None,
            recent=[],
            image_frames=[],
            face_identity=face_identity,
            face_observations=[],
        )

    # ------------------------------------------------------------------
    # 内部：独立摄像头模式的采帧循环
    # ------------------------------------------------------------------

    def _capture_loop(self) -> None:
        assert self._camera is not None
        try:
            self._camera.start()
        except Exception as exc:
            logger.error("remote_vision_camera_start_failed: %s", exc)
            self._running = False
            return

        logger.info("remote_vision_capture_loop_started")
        while self._running:
            try:
                frame = self._camera.read()
                if frame is None:
                    time.sleep(self.config.capture_interval_s)
                    continue

                with self._lock:
                    self._frame_count += 1
                    frame_count = self._frame_count
                    turn_id = f"turn-{self._turn_id_counter:04d}"

                if frame_count % self.config.upload_every_n_frames == 0:
                    self._upload_frame(frame, frame_id=frame_count, turn_id=turn_id)

            except Exception as exc:
                logger.warning("remote_vision_capture_error: %s", exc)

            time.sleep(self.config.capture_interval_s)

        logger.info("remote_vision_capture_loop_stopped")

    # ------------------------------------------------------------------
    # 内部：帧注入模式的上传循环
    # ------------------------------------------------------------------

    def _inject_loop(self) -> None:
        """消费外部注入的帧并上传，不自己读摄像头。"""
        logger.info("remote_vision_inject_loop_started")
        while self._running:
            with self._injected_frame_lock:
                frame = self._injected_frame

            if frame is not None:
                with self._lock:
                    self._frame_count += 1
                    frame_count = self._frame_count
                    turn_id = f"turn-{self._turn_id_counter:04d}"

                if frame_count % self.config.upload_every_n_frames == 0:
                    self._upload_frame(frame, frame_id=frame_count, turn_id=turn_id)

            time.sleep(self.config.capture_interval_s)

        logger.info("remote_vision_inject_loop_stopped")

    def _upload_frame(self, frame, *, frame_id: int, turn_id: str) -> None:
        try:
            import cv2  # type: ignore
        except ImportError:
            return

        assert self._http_client is not None
        ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        if not ok:
            return
        image_base64 = base64.b64encode(buf.tobytes()).decode("ascii")
        h, w = frame.shape[:2]
        payload = {
            "session_id": self.config.session_id,
            "turn_id": turn_id,
            "stream_id": self.config.stream_id,
            "frames": [
                {
                    "session_id": self.config.session_id,
                    "turn_id": turn_id,
                    "stream_id": self.config.stream_id,
                    "frame_id": frame_id,
                    "timestamp_ms": int(time.time() * 1000),
                    "width": w,
                    "height": h,
                    "mime_type": "image/jpeg",
                    "image_base64": image_base64,
                }
            ],
        }
        try:
            resp = self._http_client.post(self.config.ingest_url, json=payload)
            if resp.status_code >= 400:
                logger.warning("remote_vision_upload_failed status=%d", resp.status_code)
        except Exception as exc:
            logger.warning("remote_vision_upload_error: %s", exc)

    # ------------------------------------------------------------------
    # 内部：从缓存取人脸识别结果
    # ------------------------------------------------------------------

    def _fetch_face_identity(self, turn_id: str, *, require_fresh: bool) -> FaceIdentitySchema | None:
        if self._http_client is None:
            return None
        query_mode = (self.config.query_mode or "latest").strip().lower()
        if query_mode not in {"turn", "latest"}:
            query_mode = "latest"
        payload = {
            "session_id": self.config.session_id,
            "turn_id": turn_id,
            "stream_id": self.config.stream_id,
            "query_mode": query_mode,
            "window_ms": self.config.latest_window_ms,
            "max_frames": self.config.latest_max_frames,
        }
        with self._lock:
            min_timestamp_ms = self._fresh_epoch_started_ms
        if query_mode == "latest":
            if min_timestamp_ms is not None:
                payload["min_timestamp_ms"] = min_timestamp_ms
            if require_fresh:
                payload["reference_timestamp_ms"] = int(time.time() * 1000)
                payload["max_frame_age_ms"] = self.config.prepare_max_frame_age_ms
                payload["min_frames"] = self.config.prepare_min_frames
        started = time.perf_counter()
        log_event(
            "remote_vision_from_cache_started",
            query_mode=query_mode,
            turn_id=turn_id,
            stream_id=self.config.stream_id,
            window_ms=self.config.latest_window_ms,
            max_frames=self.config.latest_max_frames,
            min_timestamp_ms=min_timestamp_ms,
            reference_timestamp_ms=payload.get("reference_timestamp_ms"),
            require_fresh=require_fresh,
            max_frame_age_ms=self.config.prepare_max_frame_age_ms if query_mode == "latest" and require_fresh else None,
            min_frames=self.config.prepare_min_frames if query_mode == "latest" and require_fresh else None,
            timeout_seconds=self.config.from_cache_timeout_s,
        )
        try:
            resp = self._http_client.post(
                self.config.from_cache_url,
                json=payload,
                timeout=self.config.from_cache_timeout_s,
            )
            if resp.status_code != 200:
                log_event(
                    "remote_vision_from_cache_failed",
                    level="warning",
                    query_mode=query_mode,
                    turn_id=turn_id,
                    status_code=resp.status_code,
                    latency_ms=round((time.perf_counter() - started) * 1000, 2),
                )
                return None
            data = resp.json()
            fi = (data.get("face_identity") or {}).get("face_identity")
            if fi is None:
                log_event(
                    "remote_vision_from_cache_empty",
                    level="warning",
                    query_mode=query_mode,
                    turn_id=turn_id,
                    latency_ms=round((time.perf_counter() - started) * 1000, 2),
                )
                return None
            bbox_raw = fi.get("bbox")
            bbox = FaceBoxSchema(**bbox_raw) if bbox_raw else None
            face_identity = FaceIdentitySchema(
                face_detected=bool(fi.get("face_detected", False)),
                face_id=fi.get("face_id"),
                user_id=fi.get("user_id"),
                is_known=bool(fi.get("is_known", False)),
                match_confidence=fi.get("match_confidence"),
                display_name=fi.get("display_name"),
                bbox=bbox,
                source=fi.get("source"),
                embedding_model=fi.get("embedding_model"),
                seen_count=fi.get("seen_count"),
                last_seen_at=fi.get("last_seen_at"),
            )
            face_payload = data.get("face_identity") or {}
            cache_query = data.get("cache_query") or {}
            video_meta = cache_query.get("video_meta") or {}
            frame_age_ms = self._video_frame_age_ms(video_meta)
            freshness_rejected_reason = cache_query.get("freshness_rejected_reason")
            log_event(
                "remote_vision_from_cache_succeeded",
                query_mode=query_mode,
                turn_id=turn_id,
                face_detected=face_identity.face_detected,
                face_id=face_identity.face_id,
                user_id=face_identity.user_id,
                processed_frame_count=face_payload.get("processed_frame_count"),
                cached_frame_count=video_meta.get("frame_count"),
                video_first_timestamp_ms=video_meta.get("first_timestamp_ms"),
                video_last_timestamp_ms=video_meta.get("last_timestamp_ms"),
                video_last_frame_age_ms=frame_age_ms,
                min_timestamp_ms=min_timestamp_ms,
                freshness_rejected_reason=freshness_rejected_reason,
                latency_ms=round((time.perf_counter() - started) * 1000, 2),
            )
            return face_identity
        except Exception as exc:
            log_event(
                "remote_vision_from_cache_error",
                level="warning",
                query_mode=query_mode,
                turn_id=turn_id,
                error=str(exc),
                latency_ms=round((time.perf_counter() - started) * 1000, 2),
            )
            logger.warning("remote_vision_from_cache_error: %s", exc)
            return None

    @staticmethod
    def _video_frame_age_ms(video_meta: dict[str, Any]) -> int | None:
        last_timestamp_ms = video_meta.get("last_timestamp_ms")
        if last_timestamp_ms is None:
            return None
        try:
            return max(0, int(time.time() * 1000) - int(last_timestamp_ms))
        except (TypeError, ValueError):
            return None

    # ------------------------------------------------------------------
    # 内部：初始化
    # ------------------------------------------------------------------

    def _init_camera(self) -> None:
        from raspirobot.hardware.pan_tilt_face_tracker import CameraCapture, CameraConfig
        cfg = CameraConfig(
            width=self.config.camera_width,
            height=self.config.camera_height,
            use_picamera2=self.config.use_picamera2,
            cv2_device_index=self.config.cv2_device_index,
            hflip=self.config.hflip,
            vflip=self.config.vflip,
        )
        self._camera = CameraCapture(cfg)

    def _init_http(self) -> None:
        import httpx  # type: ignore
        self._http_client = httpx.Client(timeout=self.config.upload_timeout_s)
