from __future__ import annotations

import argparse
import threading
import time
from dataclasses import dataclass, field

try:
    import cv2
except Exception as exc:  # pragma: no cover - runtime dependency
    cv2 = None  # type: ignore[assignment]
    _CV2_IMPORT_ERROR = exc
else:
    _CV2_IMPORT_ERROR = None

try:
    import numpy as np
except Exception as exc:  # pragma: no cover - runtime dependency
    np = None  # type: ignore[assignment]
    _NP_IMPORT_ERROR = exc
else:
    _NP_IMPORT_ERROR = None

try:
    import mediapipe as mp
except Exception as exc:  # pragma: no cover - optional dependency
    mp = None  # type: ignore[assignment]
    _MP_IMPORT_ERROR = exc
else:
    _MP_IMPORT_ERROR = None

try:
    from adafruit_servokit import ServoKit
except Exception:  # pragma: no cover - depends on hardware runtime
    ServoKit = None  # type: ignore[assignment]

try:
    from picamera2 import Picamera2
except Exception:  # pragma: no cover - optional runtime backend
    Picamera2 = None  # type: ignore[assignment]


def _require_cv2() -> None:
    if cv2 is None:
        raise RuntimeError("opencv-python is required. Install: pip install opencv-python") from _CV2_IMPORT_ERROR


def _require_numpy() -> None:
    if np is None:
        raise RuntimeError("numpy is required. Install: pip install numpy") from _NP_IMPORT_ERROR


@dataclass(frozen=True)
class ServoSpec:
    model_name: str = "LD-3015MG"
    min_pulse_us: int = 500
    max_pulse_us: int = 2500
    actuation_range_deg: float = 180.0
    safe_min_angle_deg: float = 10.0
    safe_max_angle_deg: float = 170.0
    center_angle_deg: float = 90.0


@dataclass(frozen=True)
class PanTiltServoConfig:
    channels: int = 16
    i2c_address: int = 0x40
    frequency_hz: int = 50
    pan_channel: int = 0
    tilt_channel: int = 1
    pan_inverted: bool = True
    tilt_inverted: bool = True
    pan_zero_offset_deg: float = 0.0
    tilt_zero_offset_deg: float = 0.0
    pan_spec: ServoSpec = field(default_factory=ServoSpec)
    tilt_spec: ServoSpec = field(default_factory=ServoSpec)


@dataclass(frozen=True)
class CameraConfig:
    width: int = 320
    height: int = 240
    use_picamera2: bool = True
    cv2_device_index: int = 0
    hflip: bool = False
    vflip: bool = True


@dataclass(frozen=True)
class TrackerConfig:
    detect_scale: float = 1.0
    min_face_size: int = 40
    smooth_alpha: float = 0.26
    deadband_x_px: float = 16.0
    deadband_y_px: float = 14.0
    gain_x: float = 0.020
    gain_y: float = 0.018
    max_step_x_deg: float = 1.8
    max_step_y_deg: float = 1.2
    servo_update_interval_s: float = 0.04
    display_interval_s: float = 0.04
    lost_face_hold_frames: int = 12
    pan_control_sign: float = 1.0
    tilt_control_sign: float = -1.0


@dataclass(frozen=True)
class DetectedFace:
    x: int
    y: int
    w: int
    h: int
    tx: float
    ty: float
    source: str
    score: float


class PanTiltServoDriver:
    def __init__(self, config: PanTiltServoConfig) -> None:
        _require_numpy()
        if ServoKit is None:
            raise RuntimeError("adafruit_servokit is not installed on this runtime.")
        self.config = config
        self.kit = ServoKit(
            channels=config.channels,
            address=config.i2c_address,
            frequency=config.frequency_hz,
        )

        self.kit.servo[config.pan_channel].set_pulse_width_range(
            config.pan_spec.min_pulse_us,
            config.pan_spec.max_pulse_us,
        )
        self.kit.servo[config.tilt_channel].set_pulse_width_range(
            config.tilt_spec.min_pulse_us,
            config.tilt_spec.max_pulse_us,
        )
        self.kit.servo[config.pan_channel].actuation_range = config.pan_spec.actuation_range_deg
        self.kit.servo[config.tilt_channel].actuation_range = config.tilt_spec.actuation_range_deg

        self.pan_deg = config.pan_spec.center_angle_deg
        self.tilt_deg = config.tilt_spec.center_angle_deg
        self.pan_hw_deg = self.pan_deg
        self.tilt_hw_deg = self.tilt_deg
        self.set_pose(self.pan_deg, self.tilt_deg)

    def set_pose(self, pan_deg: float, tilt_deg: float) -> None:
        pan_deg = self._clip(pan_deg, self.config.pan_spec)
        tilt_deg = self._clip(tilt_deg, self.config.tilt_spec)

        self.pan_deg = pan_deg
        self.tilt_deg = tilt_deg

        pan_hw_target = self._clip(pan_deg + self.config.pan_zero_offset_deg, self.config.pan_spec)
        tilt_hw_target = self._clip(tilt_deg + self.config.tilt_zero_offset_deg, self.config.tilt_spec)
        self.pan_hw_deg = pan_hw_target
        self.tilt_hw_deg = tilt_hw_target

        pan_hw = self._to_hw_angle(pan_hw_target, self.config.pan_spec, self.config.pan_inverted)
        tilt_hw = self._to_hw_angle(tilt_hw_target, self.config.tilt_spec, self.config.tilt_inverted)

        self.kit.servo[self.config.pan_channel].angle = pan_hw
        self.kit.servo[self.config.tilt_channel].angle = tilt_hw

    def apply_delta(self, delta_pan_deg: float, delta_tilt_deg: float) -> None:
        self.set_pose(self.pan_deg + delta_pan_deg, self.tilt_deg + delta_tilt_deg)

    @staticmethod
    def _clip(value: float, spec: ServoSpec) -> float:
        return float(np.clip(value, spec.safe_min_angle_deg, spec.safe_max_angle_deg))

    @staticmethod
    def _to_hw_angle(angle_deg: float, spec: ServoSpec, inverted: bool) -> float:
        if not inverted:
            return angle_deg
        return float(spec.actuation_range_deg - angle_deg)


class CameraCapture:
    def __init__(self, config: CameraConfig) -> None:
        _require_cv2()
        self.config = config
        self._picam = None
        self._cap = None
        self._using_picamera2 = False

    def start(self) -> None:
        if self.config.use_picamera2 and Picamera2 is not None:
            self._start_picamera2()
            return
        self._start_cv2()

    def read(self) -> np.ndarray | None:
        if self._using_picamera2:
            assert self._picam is not None
            frame = self._picam.capture_array()
            if frame is None:
                return None
            if frame.ndim == 3 and frame.shape[2] == 4:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
            elif frame.ndim == 3 and frame.shape[2] == 3:
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            return self._apply_flip(frame)

        assert self._cap is not None
        ok, frame = self._cap.read()
        if not ok:
            return None
        return self._apply_flip(frame)

    def stop(self) -> None:
        if self._picam is not None:
            self._picam.stop()
            self._picam.close()
            self._picam = None
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def _start_picamera2(self) -> None:
        self._picam = Picamera2()
        preview = self._picam.create_preview_configuration(
            main={"format": "RGB888", "size": (self.config.width, self.config.height)}
        )
        self._picam.configure(preview)
        self._picam.start()
        self._using_picamera2 = True

    def _start_cv2(self) -> None:
        self._cap = cv2.VideoCapture(self.config.cv2_device_index)
        if not self._cap.isOpened():
            raise RuntimeError("Failed to open camera by cv2.VideoCapture.")
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.height)
        self._using_picamera2 = False

    def _apply_flip(self, frame: np.ndarray) -> np.ndarray:
        if self.config.hflip:
            frame = cv2.flip(frame, 1)
        if self.config.vflip:
            frame = cv2.flip(frame, 0)
        return frame


class FaceDetector:
    def __init__(
        self,
        *,
        detector_mode: str = "auto",
        min_face_size: int = 40,
        min_detection_confidence: float = 0.55,
        haar_scale_factor: float = 1.12,
        haar_min_neighbors: int = 5,
    ) -> None:
        _require_cv2()
        _require_numpy()

        self.detector_mode = detector_mode
        self.min_face_size = min_face_size
        self.min_detection_confidence = min_detection_confidence
        self.haar_scale_factor = haar_scale_factor
        self.haar_min_neighbors = haar_min_neighbors

        self._mp_face_detector = None
        self._face_cascade = None
        self._runtime_note = ""

        self._init_mediapipe()
        self._init_haar()

        if self.detector_mode == "mediapipe" and self._mp_face_detector is None:
            raise RuntimeError(
                "detector=mediapipe requested, but mediapipe is unavailable. "
                "Install with: pip install mediapipe"
            ) from _MP_IMPORT_ERROR

        if self.detector_mode == "haar" and self._face_cascade is None:
            raise RuntimeError("detector=haar requested, but Haar cascade load failed.")

        if self._mp_face_detector is None and self._face_cascade is None:
            raise RuntimeError("No face detector backend is available.")

    def describe(self) -> str:
        mp_state = "on" if self._mp_face_detector is not None else "off"
        haar_state = "on" if self._face_cascade is not None else "off"
        return (
            f"detector_request={self.detector_mode} mediapipe={mp_state} haar={haar_state} "
            f"min_face_size={self.min_face_size} haar_scale={self.haar_scale_factor} "
            f"haar_neighbors={self.haar_min_neighbors}"
        )

    def detect_primary(self, frame_bgr: np.ndarray) -> DetectedFace | None:
        if self.detector_mode in {"auto", "mediapipe"}:
            mp_face = self._detect_by_mediapipe(frame_bgr)
            if mp_face is not None:
                return mp_face
            if self.detector_mode == "mediapipe":
                return None

        if self.detector_mode in {"auto", "haar"}:
            return self._detect_by_haar(frame_bgr)

        return None

    def _init_mediapipe(self) -> None:
        if self.detector_mode == "haar":
            return
        if mp is None:
            self._runtime_note = "mediapipe unavailable, fallback to haar"
            return
        try:
            self._mp_face_detector = mp.solutions.face_detection.FaceDetection(
                model_selection=0,
                min_detection_confidence=self.min_detection_confidence,
            )
        except Exception as exc:
            self._runtime_note = f"mediapipe init failed, fallback to haar: {exc}"
            self._mp_face_detector = None

    def _init_haar(self) -> None:
        if self.detector_mode == "mediapipe":
            return
        face_xml = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        cascade = cv2.CascadeClassifier(face_xml)
        if cascade.empty():
            self._face_cascade = None
            return
        self._face_cascade = cascade

    def _detect_by_mediapipe(self, frame_bgr: np.ndarray) -> DetectedFace | None:
        if self._mp_face_detector is None:
            return None

        h, w = frame_bgr.shape[:2]
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        try:
            results = self._mp_face_detector.process(rgb)
        except Exception:
            return None

        if results is None or not results.detections:
            return None

        best: DetectedFace | None = None
        best_area = -1

        for det in results.detections:
            score = float(det.score[0]) if det.score else 0.0
            if score < self.min_detection_confidence:
                continue

            rb = det.location_data.relative_bounding_box
            x = max(0, int(rb.xmin * w))
            y = max(0, int(rb.ymin * h))
            bw = int(rb.width * w)
            bh = int(rb.height * h)
            bw = max(0, min(bw, w - x))
            bh = max(0, min(bh, h - y))
            if bw <= 0 or bh <= 0:
                continue

            tx = float(x + bw / 2.0)
            ty = float(y + bh * 0.45)

            keypoints = det.location_data.relative_keypoints
            if keypoints and len(keypoints) >= 3:
                nose = keypoints[2]
                tx = float(np.clip(nose.x * w, 0, w - 1))
                ty = float(np.clip(nose.y * h, 0, h - 1))

            area = bw * bh
            if area > best_area:
                best_area = area
                best = DetectedFace(
                    x=x,
                    y=y,
                    w=bw,
                    h=bh,
                    tx=tx,
                    ty=ty,
                    source="mediapipe",
                    score=score,
                )

        return best

    def _detect_by_haar(self, frame_bgr: np.ndarray) -> DetectedFace | None:
        if self._face_cascade is None:
            return None

        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)
        faces = self._face_cascade.detectMultiScale(
            gray,
            scaleFactor=self.haar_scale_factor,
            minNeighbors=self.haar_min_neighbors,
            minSize=(self.min_face_size, self.min_face_size),
        )
        if len(faces) == 0:
            return None

        x, y, bw, bh = max(faces, key=lambda box: box[2] * box[3])
        return DetectedFace(
            x=int(x),
            y=int(y),
            w=int(bw),
            h=int(bh),
            tx=float(x + bw / 2.0),
            ty=float(y + bh * 0.42),
            source="haar",
            score=1.0,
        )


class FaceTrackingPanTiltRunner:
    def __init__(
        self,
        *,
        servo: PanTiltServoDriver,
        camera: CameraCapture,
        detector: FaceDetector,
        config: TrackerConfig,
        show_window: bool = True,
        frame_sink: object | None = None,
    ) -> None:
        self.servo = servo
        self.camera = camera
        self.detector = detector
        self.config = config
        self.show_window = show_window
        self._stop_event = threading.Event()
        # frame_sink: 实现了 inject_frame(frame) 的对象，用于共享摄像头帧
        self._frame_sink = frame_sink

    def request_stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        self.camera.start()
        target_x = 0.0
        target_y = 0.0
        lost_frames = 0
        last_source = "none"
        last_score = 0.0
        last_servo_ts = time.time()
        last_fps_ts = time.time()
        last_frame_show_ts = time.time()

        try:
            while not self._stop_event.is_set():
                frame = self.camera.read()
                if frame is None:
                    continue

                # 共享帧给视频上传模块（如 RemoteVisionContextProvider）
                if self._frame_sink is not None:
                    try:
                        self._frame_sink.inject_frame(frame)
                    except Exception:
                        pass

                h, w = frame.shape[:2]
                if target_x <= 0.0 and target_y <= 0.0:
                    target_x = w / 2.0
                    target_y = h / 2.0

                detect_frame = frame
                scale_back = 1.0
                if 0.0 < self.config.detect_scale < 1.0:
                    detect_frame = cv2.resize(
                        frame,
                        None,
                        fx=self.config.detect_scale,
                        fy=self.config.detect_scale,
                        interpolation=cv2.INTER_LINEAR,
                    )
                    scale_back = 1.0 / self.config.detect_scale

                face = self.detector.detect_primary(detect_frame)
                if face is not None:
                    x = face.x
                    y = face.y
                    fw = face.w
                    fh = face.h
                    cx = face.tx
                    cy = face.ty
                    if scale_back != 1.0:
                        x = int(x * scale_back)
                        y = int(y * scale_back)
                        fw = int(fw * scale_back)
                        fh = int(fh * scale_back)
                        cx = float(cx * scale_back)
                        cy = float(cy * scale_back)

                    target_x = (1.0 - self.config.smooth_alpha) * target_x + self.config.smooth_alpha * cx
                    target_y = (1.0 - self.config.smooth_alpha) * target_y + self.config.smooth_alpha * cy
                    lost_frames = 0
                    last_source = face.source
                    last_score = face.score

                    cv2.rectangle(frame, (x, y), (x + fw, y + fh), (0, 70, 255), 2)
                    cv2.circle(frame, (int(cx), int(cy)), 4, (0, 255, 0), -1)
                    cv2.circle(frame, (int(target_x), int(target_y)), 4, (255, 255, 0), -1)
                else:
                    lost_frames += 1

                err_x = target_x - (w / 2.0)
                err_y = target_y - (h / 2.0)

                delta_pan = self._control_step(
                    error_px=err_x,
                    deadband_px=self.config.deadband_x_px,
                    gain=self.config.gain_x,
                    max_step_deg=self.config.max_step_x_deg,
                    sign=self.config.pan_control_sign,
                )
                delta_tilt = self._control_step(
                    error_px=err_y,
                    deadband_px=self.config.deadband_y_px,
                    gain=self.config.gain_y,
                    max_step_deg=self.config.max_step_y_deg,
                    sign=self.config.tilt_control_sign,
                )

                now = time.time()
                if lost_frames <= self.config.lost_face_hold_frames and now - last_servo_ts >= self.config.servo_update_interval_s:
                    self.servo.apply_delta(delta_pan, delta_tilt)
                    last_servo_ts = now

                fps = 1.0 / max(now - last_fps_ts, 1e-6)
                last_fps_ts = now
                self._draw_hud(frame, err_x, err_y, fps, last_source, last_score, lost_frames)

                if self.show_window and now - last_frame_show_ts >= self.config.display_interval_s:
                    cv2.imshow("PanTilt Face Tracking", frame)
                    last_frame_show_ts = now
                    key = cv2.waitKey(1) & 0xFF
                    if key == ord("q"):
                        self._stop_event.set()
                        break
        finally:
            self.camera.stop()
            if self.show_window:
                cv2.destroyAllWindows()

    def _draw_hud(
        self,
        frame: np.ndarray,
        err_x: float,
        err_y: float,
        fps: float,
        source: str,
        score: float,
        lost_frames: int,
    ) -> None:
        h, w = frame.shape[:2]
        cv2.line(frame, (w // 2, 0), (w // 2, h), (0, 255, 255), 1)
        cv2.line(frame, (0, h // 2), (w, h // 2), (0, 255, 255), 1)
        cv2.putText(frame, f"fps:{fps:.1f}", (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)
        cv2.putText(frame, f"err:({err_x:.1f},{err_y:.1f})", (8, 46), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)
        cv2.putText(frame, f"pan:{self.servo.pan_deg:.1f} tilt:{self.servo.tilt_deg:.1f}", (8, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)
        cv2.putText(
            frame,
            f"face:{source} conf:{score:.2f} lost:{lost_frames}",
            (8, 94),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 255, 255),
            2,
        )

    @staticmethod
    def _control_step(
        *,
        error_px: float,
        deadband_px: float,
        gain: float,
        max_step_deg: float,
        sign: float,
    ) -> float:
        abs_err = abs(error_px)
        if abs_err <= deadband_px:
            return 0.0
        eff = abs_err - deadband_px
        step = min(max_step_deg, gain * eff)
        return float(-np.sign(error_px) * step * sign)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="2-axis pan-tilt face tracking for Raspberry Pi robot head.")
    parser.add_argument("--camera-width", type=int, default=320)
    parser.add_argument("--camera-height", type=int, default=240)
    parser.add_argument("--detect-scale", type=float, default=1.0)
    parser.add_argument("--min-face-size", type=int, default=40)

    parser.add_argument("--detector", choices=["auto", "haar", "mediapipe"], default="auto")
    parser.add_argument("--min-detection-confidence", type=float, default=0.55)
    parser.add_argument("--haar-scale-factor", type=float, default=1.12)
    parser.add_argument("--haar-min-neighbors", type=int, default=5)

    parser.add_argument("--pan-channel", type=int, default=0)
    parser.add_argument("--tilt-channel", type=int, default=1)
    parser.add_argument("--i2c-address", type=lambda x: int(x, 0), default=0x40)
    parser.add_argument("--frequency", type=int, default=50)

    parser.add_argument("--no-picamera2", action="store_true", help="Use cv2.VideoCapture backend")
    parser.add_argument("--device-index", type=int, default=0, help="cv2.VideoCapture index when --no-picamera2")

    parser.add_argument("--no-window", action="store_true", help="Disable OpenCV window display")

    parser.add_argument("--pan-min-angle", type=float, default=10.0)
    parser.add_argument("--pan-max-angle", type=float, default=170.0)
    parser.add_argument("--tilt-min-angle", type=float, default=10.0)
    parser.add_argument("--tilt-max-angle", type=float, default=170.0)
    parser.add_argument("--center-pan", type=float, default=90.0)
    parser.add_argument("--center-tilt", type=float, default=90.0)
    parser.add_argument("--pan-zero-offset", type=float, default=0.0, help="Mechanical zero trim for pan axis (deg)")
    parser.add_argument("--tilt-zero-offset", type=float, default=0.0, help="Mechanical zero trim for tilt axis (deg)")
    parser.add_argument("--servo-min-pulse", type=int, default=500)
    parser.add_argument("--servo-max-pulse", type=int, default=2500)
    parser.add_argument("--actuation-range", type=float, default=180.0)

    parser.set_defaults(pan_inverted=True, tilt_inverted=True)
    parser.add_argument("--pan-inverted", dest="pan_inverted", action="store_true", help="Invert pan axis")
    parser.add_argument("--no-pan-inverted", dest="pan_inverted", action="store_false", help="Do not invert pan axis")
    parser.add_argument("--tilt-inverted", dest="tilt_inverted", action="store_true", help="Invert tilt axis")
    parser.add_argument("--no-tilt-inverted", dest="tilt_inverted", action="store_false", help="Do not invert tilt axis")

    return parser


def main() -> None:
    args = build_arg_parser().parse_args()

    _require_cv2()
    _require_numpy()

    servo_spec_pan = ServoSpec(
        model_name="LD-3015MG",
        min_pulse_us=args.servo_min_pulse,
        max_pulse_us=args.servo_max_pulse,
        actuation_range_deg=args.actuation_range,
        safe_min_angle_deg=args.pan_min_angle,
        safe_max_angle_deg=args.pan_max_angle,
        center_angle_deg=args.center_pan,
    )
    servo_spec_tilt = ServoSpec(
        model_name="LD-3015MG",
        min_pulse_us=args.servo_min_pulse,
        max_pulse_us=args.servo_max_pulse,
        actuation_range_deg=args.actuation_range,
        safe_min_angle_deg=args.tilt_min_angle,
        safe_max_angle_deg=args.tilt_max_angle,
        center_angle_deg=args.center_tilt,
    )

    servo_cfg = PanTiltServoConfig(
        i2c_address=args.i2c_address,
        frequency_hz=args.frequency,
        pan_channel=args.pan_channel,
        tilt_channel=args.tilt_channel,
        pan_inverted=args.pan_inverted,
        tilt_inverted=args.tilt_inverted,
        pan_zero_offset_deg=args.pan_zero_offset,
        tilt_zero_offset_deg=args.tilt_zero_offset,
        pan_spec=servo_spec_pan,
        tilt_spec=servo_spec_tilt,
    )
    camera_cfg = CameraConfig(
        width=args.camera_width,
        height=args.camera_height,
        use_picamera2=not args.no_picamera2,
        cv2_device_index=args.device_index,
    )
    tracker_cfg = TrackerConfig(
        detect_scale=args.detect_scale,
        min_face_size=args.min_face_size,
    )

    servo = PanTiltServoDriver(servo_cfg)
    camera = CameraCapture(camera_cfg)
    detector = FaceDetector(
        detector_mode=args.detector,
        min_face_size=tracker_cfg.min_face_size,
        min_detection_confidence=args.min_detection_confidence,
        haar_scale_factor=args.haar_scale_factor,
        haar_min_neighbors=args.haar_min_neighbors,
    )

    runner = FaceTrackingPanTiltRunner(
        servo=servo,
        camera=camera,
        detector=detector,
        config=tracker_cfg,
        show_window=not args.no_window,
    )

    print("[face-track] started. Press 'q' in window to quit.")
    print(
        "[face-track] servo model=%s pulse=%d-%dus range=%.1f"
        % (
            servo_cfg.pan_spec.model_name,
            servo_cfg.pan_spec.min_pulse_us,
            servo_cfg.pan_spec.max_pulse_us,
            servo_cfg.pan_spec.actuation_range_deg,
        )
    )
    print(
        "[face-track] zero-offset pan=%+.1f tilt=%+.1f"
        % (servo_cfg.pan_zero_offset_deg, servo_cfg.tilt_zero_offset_deg)
    )
    print(f"[face-track] {detector.describe()}")
    if mp is None:
        print("[face-track] mediapipe not installed, using haar only")
    runner.run()


if __name__ == "__main__":
    main()
