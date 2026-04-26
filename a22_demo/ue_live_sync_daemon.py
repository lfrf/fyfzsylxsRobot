#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UE live sync daemon:
- watches latest_turn_id.txt
- when a new turn arrives, applies latest audio + viseme to BP_RemoteAudioPlayer

Usage in Unreal console:
  Cmd: py "C:/Users/FYF/Documents/GitHub/FuChuangSai_A22/a22_demo/ue_live_sync_daemon.py"

Optional stop:
  Cmd: py "C:/Users/FYF/Documents/GitHub/FuChuangSai_A22/a22_demo/ue_live_sync_daemon.py" --stop
"""

from __future__ import annotations

import argparse
import json
import runpy
import sys
import time
from pathlib import Path
from typing import Any

import unreal

_GLOBAL_HANDLE_KEY = "__A22_UE_LIVE_SYNC_HANDLE__"
_GLOBAL_LAST_APPLIED_KEY = "__A22_UE_LIVE_SYNC_LAST_APPLIED_TURN__"
_GLOBAL_HANDLES_KEY = "__A22_UE_LIVE_SYNC_ALL_HANDLES__"
_GLOBAL_BUSY_KEY = "__A22_UE_LIVE_SYNC_BUSY__"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--stream-dir",
        default=r"C:\Users\FYF\Documents\GitHub\FuChuangSai_A22\tmp\ue_a2f_runtime\demo_s1\demo_stream_1",
    )
    parser.add_argument(
        "--sync-script",
        default=r"C:\Users\FYF\Documents\GitHub\FuChuangSai_A22\a22_demo\ue_sync_latest_to_actor.py",
    )
    parser.add_argument("--interval-seconds", type=float, default=0.5)
    parser.add_argument("--actor-label", default="BP_RemoteAudioPlayer")
    parser.add_argument(
        "--disable-media-restart",
        action="store_true",
        help="Pass --disable-media-restart to ue_sync_latest_to_actor.py",
    )
    parser.add_argument(
        "--status-file",
        default="",
        help="Optional status json path. Default: <stream-dir>/ue_live_sync_status.json",
    )
    parser.add_argument("--once", action="store_true", help="Apply current latest turn once then exit.")
    parser.add_argument("--stop", action="store_true")
    known, _ = parser.parse_known_args(sys.argv[1:])
    return known


def _log(message: str) -> None:
    unreal.log("[ue_live_sync_daemon] " + message)


def _warn(message: str) -> None:
    unreal.log_warning("[ue_live_sync_daemon] " + message)


def _status_path(args: argparse.Namespace) -> Path:
    if args.status_file:
        return Path(args.status_file).expanduser()
    return Path(args.stream_dir).expanduser() / "ue_live_sync_status.json"


def _write_status(extra: dict[str, Any]) -> None:
    args = _STATE.get("args")
    if args is None:
        return
    path = _status_path(args)
    payload = {
        "ts_ms": int(time.time() * 1000),
        "state": {
            "running": _STATE.get("handle") is not None,
            "last_check_ts": _STATE.get("last_check_ts"),
            "last_seen_turn": _STATE.get("last_seen_turn"),
            "last_applied_turn": _STATE.get("last_applied_turn"),
        },
    }
    payload.update(extra)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def _read_turn_id(turn_path: Path) -> int | None:
    try:
        raw = turn_path.read_text(encoding="utf-8").strip()
        if not raw:
            return None
        return int(raw)
    except Exception:
        return None


def _run_sync(sync_script: Path, stream_dir: Path, actor_label: str) -> tuple[bool, str]:
    argv_backup = list(sys.argv)
    try:
        sys.argv = [
            str(sync_script),
            "--stream-dir",
            str(stream_dir),
            "--actor-label",
            actor_label,
            "--apply-viseme-inplace",
        ]
        args = _STATE.get("args")
        if args is not None and bool(getattr(args, "disable_media_restart", False)):
            sys.argv.append("--disable-media-restart")
        runpy.run_path(str(sync_script), run_name="__main__")
        return True, "ok"
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 0
        if code == 0:
            return True, "ok"
        return False, f"sync script exited with code={code}"
    except Exception as exc:  # pragma: no cover - runtime only
        return False, f"{type(exc).__name__}: {exc}"
    finally:
        sys.argv = argv_backup


_STATE: dict[str, Any] = {
    "handle": None,
    "last_check_ts": 0.0,
    "last_seen_turn": None,
    "last_applied_turn": None,
    "args": None,
}


def _get_global_handle():
    try:
        return getattr(unreal, _GLOBAL_HANDLE_KEY, None)
    except Exception:
        return None


def _set_global_handle(handle) -> None:
    try:
        setattr(unreal, _GLOBAL_HANDLE_KEY, handle)
    except Exception:
        pass


def _get_global_handles() -> list[Any]:
    try:
        handles = getattr(unreal, _GLOBAL_HANDLES_KEY, None)
    except Exception:
        handles = None
    if not isinstance(handles, list):
        return []
    return list(handles)


def _set_global_handles(handles: list[Any]) -> None:
    try:
        setattr(unreal, _GLOBAL_HANDLES_KEY, list(handles))
    except Exception:
        pass


def _add_global_handle(handle) -> None:
    handles = _get_global_handles()
    if handle not in handles:
        handles.append(handle)
    _set_global_handles(handles)


def _clear_global_busy() -> None:
    try:
        setattr(unreal, _GLOBAL_BUSY_KEY, False)
    except Exception:
        pass


def _try_enter_global_busy() -> bool:
    try:
        busy = bool(getattr(unreal, _GLOBAL_BUSY_KEY, False))
    except Exception:
        busy = False
    if busy:
        return False
    try:
        setattr(unreal, _GLOBAL_BUSY_KEY, True)
    except Exception:
        pass
    return True


def _get_global_last_applied_turn():
    try:
        return getattr(unreal, _GLOBAL_LAST_APPLIED_KEY, None)
    except Exception:
        return None


def _set_global_last_applied_turn(turn_id) -> None:
    try:
        setattr(unreal, _GLOBAL_LAST_APPLIED_KEY, turn_id)
    except Exception:
        pass


def _stop_daemon() -> None:
    handles = []
    local_handle = _STATE.get("handle")
    if local_handle is not None:
        handles.append(local_handle)
    global_handle = _get_global_handle()
    if global_handle is not None and global_handle != local_handle:
        handles.append(global_handle)
    for h in _get_global_handles():
        if h not in handles:
            handles.append(h)

    stopped_any = False
    for handle in handles:
        try:
            unreal.unregister_slate_post_tick_callback(handle)
            stopped_any = True
        except Exception as exc:  # pragma: no cover - runtime only
            _warn(f"failed to unregister callback: {type(exc).__name__}: {exc}")
    if stopped_any:
        _log("stopped")
        _write_status({"event": "stopped"})
    _STATE["handle"] = None
    _set_global_handle(None)
    _set_global_handles([])
    _clear_global_busy()


def _tick(delta_seconds: float) -> None:
    _ = delta_seconds
    if not _try_enter_global_busy():
        return
    args: argparse.Namespace = _STATE["args"]
    try:
        now = time.time()
        if now - float(_STATE.get("last_check_ts") or 0.0) < max(0.1, float(args.interval_seconds)):
            return
        _STATE["last_check_ts"] = now

        stream_dir = Path(args.stream_dir).expanduser()
        turn_path = stream_dir / "latest_turn_id.txt"
        sync_script = Path(args.sync_script).expanduser()
        if not turn_path.exists():
            _write_status({"event": "waiting_turn_file", "turn_path": str(turn_path)})
            return
        if not sync_script.exists():
            _warn(f"sync script not found: {sync_script}")
            _write_status({"event": "sync_script_missing", "sync_script": str(sync_script)})
            return

        turn_id = _read_turn_id(turn_path)
        if turn_id is None:
            return

        if _STATE["last_seen_turn"] != turn_id:
            _STATE["last_seen_turn"] = turn_id
            _log(f"detected new turn_id={turn_id}")
            _write_status({"event": "detected", "turn_id": turn_id})

        if _STATE["last_applied_turn"] == turn_id:
            return
        global_last = _get_global_last_applied_turn()
        if global_last == turn_id:
            _STATE["last_applied_turn"] = turn_id
            return

        ok, info = _run_sync(sync_script, stream_dir, args.actor_label)
        if ok:
            _STATE["last_applied_turn"] = turn_id
            _set_global_last_applied_turn(turn_id)
            _log(f"applied turn_id={turn_id}")
            _write_status({"event": "applied", "turn_id": turn_id, "info": info})
        else:
            _warn(f"apply failed turn_id={turn_id}: {info}")
            _write_status({"event": "apply_failed", "turn_id": turn_id, "error": info})
    finally:
        _clear_global_busy()


def main() -> int:
    args = parse_args()
    _STATE["args"] = args

    if args.stop:
        _stop_daemon()
        return 0

    if args.once:
        _STATE["last_check_ts"] = 0.0
        _tick(0.0)
        _write_status({"event": "once_done"})
        return 0

    # Restart daemon if already running.
    _stop_daemon()

    try:
        handle = unreal.register_slate_post_tick_callback(_tick)
        _STATE["handle"] = handle
        _set_global_handle(handle)
        _add_global_handle(handle)
        _STATE["last_check_ts"] = 0.0
        _STATE["last_seen_turn"] = None
        _STATE["last_applied_turn"] = None
    except Exception as exc:  # pragma: no cover - runtime only
        _warn(f"failed to register tick callback: {type(exc).__name__}: {exc}")
        _write_status({"event": "register_failed", "error": f"{type(exc).__name__}: {exc}"})
        return 1

    _log(
        "started "
        + f"stream_dir={args.stream_dir} "
        + f"interval={args.interval_seconds}s "
        + f"actor_label={args.actor_label}"
    )
    _write_status(
        {
            "event": "started",
            "stream_dir": args.stream_dir,
            "sync_script": args.sync_script,
            "interval_seconds": args.interval_seconds,
            "actor_label": args.actor_label,
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
