from __future__ import annotations

import argparse
import time
from pathlib import Path

try:
    import cv2
except Exception as exc:  # pragma: no cover - runtime dependency
    cv2 = None  # type: ignore[assignment]
    _CV2_IMPORT_ERROR = exc
else:
    _CV2_IMPORT_ERROR = None

from raspirobot.hardware.pan_tilt_face_tracker import CameraCapture, CameraConfig


def _require_cv2() -> None:
    if cv2 is None:
        raise RuntimeError("opencv-python is required. Install: pip install opencv-python") from _CV2_IMPORT_ERROR


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Standalone CSI camera probe for Raspberry Pi.")
    parser.add_argument("--camera-width", type=int, default=320)
    parser.add_argument("--camera-height", type=int, default=240)
    parser.add_argument("--no-picamera2", action="store_true", help="Use cv2.VideoCapture backend")
    parser.add_argument("--device-index", type=int, default=0, help="cv2.VideoCapture index when --no-picamera2")
    parser.add_argument("--no-hflip", dest="hflip", action="store_false", help="Disable horizontal flip")
    parser.add_argument("--no-vflip", dest="vflip", action="store_false", help="Disable vertical flip")
    parser.set_defaults(hflip=False, vflip=True)
    parser.add_argument("--frames", type=int, default=0, help="Number of frames to capture; 0 means unlimited")
    parser.add_argument("--save-dir", type=str, default="", help="Optional directory to save JPEG frames")
    parser.add_argument("--save-every", type=int, default=30, help="Save one frame every N captured frames")
    parser.add_argument("--preview", action="store_true", help="Show a preview window")
    parser.add_argument("--interval-ms", type=int, default=0, help="Sleep between frames in milliseconds")
    return parser


def main() -> None:
    _require_cv2()
    args = build_arg_parser().parse_args()

    save_dir = Path(args.save_dir).expanduser().resolve() if args.save_dir else None
    if save_dir is not None:
        save_dir.mkdir(parents=True, exist_ok=True)

    camera_cfg = CameraConfig(
        width=args.camera_width,
        height=args.camera_height,
        use_picamera2=not args.no_picamera2,
        cv2_device_index=args.device_index,
        hflip=args.hflip,
        vflip=args.vflip,
    )
    camera = CameraCapture(camera_cfg)

    print("[camera-probe] starting")
    print(
        "[camera-probe] config width=%d height=%d backend=%s device_index=%d hflip=%s vflip=%s"
        % (
            camera_cfg.width,
            camera_cfg.height,
            "picamera2" if camera_cfg.use_picamera2 else "cv2",
            camera_cfg.cv2_device_index,
            camera_cfg.hflip,
            camera_cfg.vflip,
        )
    )

    camera.start()
    print("[camera-probe] camera started")

    start_ts = time.time()
    frame_count = 0
    saved_count = 0

    try:
        while True:
            frame = camera.read()
            if frame is None:
                print("[camera-probe] frame=None")
                continue

            frame_count += 1
            now_ts = time.time()
            fps = frame_count / max(now_ts - start_ts, 1e-6)
            h, w = frame.shape[:2]
            print(
                "[camera-probe] frame=%d size=%dx%d fps=%.2f"
                % (frame_count, w, h, fps)
            )

            if save_dir is not None and args.save_every > 0 and frame_count % args.save_every == 0:
                file_path = save_dir / f"frame_{frame_count:06d}.jpg"
                ok = cv2.imwrite(str(file_path), frame)
                if ok:
                    saved_count += 1
                    print(f"[camera-probe] saved {file_path}")
                else:
                    print(f"[camera-probe] failed to save {file_path}")

            if args.preview:
                cv2.imshow("camera-probe", frame)
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    print("[camera-probe] quit by user")
                    break

            if args.frames > 0 and frame_count >= args.frames:
                print(f"[camera-probe] reached frame limit: {args.frames}")
                break

            if args.interval_ms > 0:
                time.sleep(args.interval_ms / 1000.0)
    finally:
        camera.stop()
        if args.preview:
            cv2.destroyAllWindows()
        elapsed = time.time() - start_ts
        print(
            "[camera-probe] stopped frames=%d saved=%d elapsed=%.2fs"
            % (frame_count, saved_count, elapsed)
        )


if __name__ == "__main__":
    main()
