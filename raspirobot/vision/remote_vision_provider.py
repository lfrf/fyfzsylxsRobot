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
from dataclasses import dataclass, field
from typing import Any

from shared.contracts.schemas import FaceBoxSchema, FaceIdentitySchema, FaceObservationSchema, VisionContext

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
    from_cache_timeout_s: float = 10.0


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

    def stop(self) -> None:
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=3.0)
            self._thread = None
        if self._camera is not None:
            try:
                self._camera.stop()
            except Exception:
                pass
            self._camera = None
        if self._http_client is not None:
            try:
                self._http_client.close()
            except Exception:
                pass
            self._http_client = None
        with self._injected_frame_lock:
            self._injected_frame = None

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

        face_identity = self._fetch_face_identity(turn_id)
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

    def _fetch_face_identity(self, turn_id: str) -> FaceIdentitySchema | None:
        if self._http_client is None:
            return None
        try:
            resp = self._http_client.post(
                self.config.from_cache_url,
                json={
                    "session_id": self.config.session_id,
                    "turn_id": turn_id,
                    "stream_id": self.config.stream_id,
                },
                timeout=self.config.from_cache_timeout_s,
            )
            if resp.status_code != 200:
                logger.warning("remote_vision_from_cache_failed status=%d", resp.status_code)
                return None
            data = resp.json()
            fi = (data.get("face_identity") or {}).get("face_identity")
            if fi is None:
                return None
            bbox_raw = fi.get("bbox")
            bbox = FaceBoxSchema(**bbox_raw) if bbox_raw else None
            return FaceIdentitySchema(
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
        except Exception as exc:
            logger.warning("remote_vision_from_cache_error: %s", exc)
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
