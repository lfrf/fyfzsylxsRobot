from __future__ import annotations

import argparse
import base64
import json
import time
from pathlib import Path

try:
    import cv2
except Exception as exc:  # pragma: no cover - runtime dependency
    cv2 = None  # type: ignore[assignment]
    _CV2_IMPORT_ERROR = exc
else:
    _CV2_IMPORT_ERROR = None

try:
    import httpx
except Exception as exc:  # pragma: no cover - runtime dependency
    httpx = None  # type: ignore[assignment]
    _HTTPX_IMPORT_ERROR = exc
else:
    _HTTPX_IMPORT_ERROR = None

from raspirobot.hardware.pan_tilt_face_tracker import CameraCapture, CameraConfig


def _require_cv2() -> None:
    if cv2 is None:
        raise RuntimeError("opencv-python is required. Install: pip install opencv-python") from _CV2_IMPORT_ERROR


def _require_httpx() -> None:
    if httpx is None:
        raise RuntimeError("httpx is required. Install: pip install httpx") from _HTTPX_IMPORT_ERROR


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
    parser.add_argument("--upload-url", type=str, default="", help="Optional HTTP endpoint for single-frame upload test")
    parser.add_argument("--session-id", type=str, default="demo-session-001")
    parser.add_argument("--turn-id", type=str, default="turn-0001")
    parser.add_argument("--stream-id", type=str, default="video-001")
    parser.add_argument("--upload-every", type=int, default=1, help="Upload every N frames when --upload-url is set")
    parser.add_argument("--upload-timeout", type=float, default=10.0, help="HTTP timeout seconds for upload")
    parser.add_argument("--upload-batch-size", type=int, default=1, help="Frames per upload request; 1 means single-frame test")
    return parser


def _encode_jpeg_base64(frame) -> str:
    ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
    if not ok:
        raise RuntimeError("Failed to encode frame as JPEG")
    jpeg_bytes = buf.tobytes()
    return base64.b64encode(jpeg_bytes).decode("ascii")


def main() -> None:
    _require_cv2()
    args = build_arg_parser().parse_args()

    save_dir = Path(args.save_dir).expanduser().resolve() if args.save_dir else None
    if save_dir is not None:
        save_dir.mkdir(parents=True, exist_ok=True)

    uploader = None
    if args.upload_url:
        _require_httpx()
        uploader = httpx.Client(timeout=args.upload_timeout)

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
    if args.upload_url:
        print(
            "[camera-probe] upload url=%s session_id=%s turn_id=%s stream_id=%s upload_every=%d batch_size=%d"
            % (
                args.upload_url,
                args.session_id,
                args.turn_id,
                args.stream_id,
                args.upload_every,
                args.upload_batch_size,
            )
        )

    camera.start()
    print("[camera-probe] camera started")

    start_ts = time.time()
    frame_count = 0
    saved_count = 0
    uploaded_count = 0
    pending_batch: list[dict[str, object]] = []

    try:
        while True:
            frame = camera.read()
            if frame is None:
                print("[camera-probe] frame=None")
                continue

            frame_count += 1
            now_ts = time.time()
            timestamp_ms = int(now_ts * 1000)
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

            if args.upload_url and args.upload_every > 0 and frame_count % args.upload_every == 0:
                image_base64, jpeg_size = _encode_jpeg_base64(frame)
                pending_batch.append(
                    {
                        "session_id": args.session_id,
                        "turn_id": args.turn_id,
                        "stream_id": args.stream_id,
                        "frame_id": frame_count,
                        "timestamp_ms": timestamp_ms,
                        "width": w,
                        "height": h,
                        "mime_type": "image/jpeg",
                        "image_base64": image_base64,
                    }
                )

                should_flush = len(pending_batch) >= max(1, args.upload_batch_size)
                if should_flush:
                    payload = {
                        "session_id": args.session_id,
                        "turn_id": args.turn_id,
                        "stream_id": args.stream_id,
                        "frames": pending_batch,
                    }
                    response = uploader.post(args.upload_url, json=payload)
                    if response.status_code >= 400:
                        print(f"[camera-probe] upload failed status={response.status_code}")
                        print("[camera-probe] upload response text=" + response.text)
                        response.raise_for_status()
                    uploaded_count += len(pending_batch)
                    print(
                        "[camera-probe] uploaded batch size=%d status=%d"
                        % (len(pending_batch), response.status_code)
                    )
                    try:
                        print("[camera-probe] upload response=" + json.dumps(response.json(), ensure_ascii=False))
                    except Exception:
                        print("[camera-probe] upload response text=" + response.text)
                    pending_batch = []

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
        if uploader is not None:
            uploader.close()
        camera.stop()
        if args.preview:
            cv2.destroyAllWindows()
        if uploader is not None and pending_batch:
            payload = {
                "session_id": args.session_id,
                "turn_id": args.turn_id,
                "stream_id": args.stream_id,
                "frames": pending_batch,
            }
            response = uploader.post(args.upload_url, json=payload)
            if response.status_code >= 400:
                print(f"[camera-probe] upload failed status={response.status_code}")
                print("[camera-probe] upload response text=" + response.text)
                response.raise_for_status()
            uploaded_count += len(pending_batch)
            print(
                "[camera-probe] uploaded final batch size=%d status=%d"
                % (len(pending_batch), response.status_code)
            )
            try:
                print("[camera-probe] upload response=" + json.dumps(response.json(), ensure_ascii=False))
            except Exception:
                print("[camera-probe] upload response text=" + response.text)
        elapsed = time.time() - start_ts
        print(
            "[camera-probe] stopped frames=%d saved=%d uploaded=%d elapsed=%.2fs"
            % (frame_count, saved_count, uploaded_count, elapsed)
        )


if __name__ == "__main__":
    main()
