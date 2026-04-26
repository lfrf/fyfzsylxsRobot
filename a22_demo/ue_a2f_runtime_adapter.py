#!/usr/bin/env python3
"""
UE/A2F Runtime Adapter

Consumes UDP packets emitted by a22_demo/avatar_ws_bridge.py and builds
per-turn runtime bundles for renderer-side playback.

Primary goals:
- eat audio_ready + motion_plan reliably
- keep turn identity strict: session_id + stream_id + turn_id
- produce deterministic bundle files for UE/A2F runtime integration
- optionally forward normalized bundles to downstream HTTP gateways
"""

from __future__ import annotations

import argparse
import base64
import json
import socket
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Consume avatar bridge packets and build UE/A2F runtime bundles.")
    parser.add_argument("--listen-host", default="127.0.0.1", help="UDP listen host.")
    parser.add_argument("--listen-port", type=int, default=19310, help="UDP listen port.")
    parser.add_argument(
        "--output-dir",
        default="/root/autodl-tmp/a22/tmp/ue_a2f_runtime",
        help="Directory to persist normalized turn bundles.",
    )
    parser.add_argument(
        "--session-id",
        default="",
        help="Optional session filter. Empty means accept all sessions.",
    )
    parser.add_argument(
        "--stream-id",
        default="",
        help="Optional stream filter. Empty means accept all streams.",
    )
    parser.add_argument(
        "--ue-http-target",
        default="",
        help="Optional HTTP endpoint to receive normalized UE payload (POST JSON).",
    )
    parser.add_argument(
        "--a2f-http-target",
        default="",
        help="Optional HTTP endpoint to receive normalized A2F payload (POST JSON).",
    )
    parser.add_argument(
        "--http-timeout-seconds",
        type=float,
        default=3.0,
        help="Timeout for optional downstream HTTP push.",
    )
    parser.add_argument(
        "--strict-order",
        action="store_true",
        help="If enabled, mark turn invalid when event order is broken.",
    )
    return parser.parse_args()


@dataclass
class TurnState:
    session_id: str
    stream_id: str
    turn_id: int
    emotion_style: str | None = None
    turn_start_seen: bool = False
    audio_ready_seen: bool = False
    motion_plan_seen: bool = False
    turn_end_seen: bool = False
    events: list[str] = field(default_factory=list)
    audio: dict[str, Any] = field(default_factory=dict)
    viseme_seq: list[dict[str, Any]] = field(default_factory=list)
    expression_seq: list[dict[str, Any]] = field(default_factory=list)
    motion_seq: list[dict[str, Any]] = field(default_factory=list)
    invalid_reason: str | None = None


def _turn_key(session_id: str, stream_id: str, turn_id: int) -> str:
    return f"{session_id}::{stream_id}::{turn_id}"


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(value, max_value))


def _json_post(url: str, payload: dict[str, Any], timeout_seconds: float) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(req, timeout=timeout_seconds):
        pass


class RuntimeAdapter:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.output_dir = Path(args.output_dir).expanduser()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.turns: dict[str, TurnState] = {}

    def run(self) -> int:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((self.args.listen_host, self.args.listen_port))
        print(
            f"[adapter] listening udp://{self.args.listen_host}:{self.args.listen_port} "
            f"-> {self.output_dir}",
            flush=True,
        )
        while True:
            packet_bytes, remote_addr = sock.recvfrom(2_000_000)
            try:
                text = packet_bytes.decode("utf-8")
                bridge_packet = json.loads(text)
            except Exception as exc:
                print(f"[adapter] drop invalid packet from {remote_addr}: {type(exc).__name__}: {exc}", flush=True)
                continue
            self._handle_bridge_packet(bridge_packet)

    def _handle_bridge_packet(self, bridge_packet: dict[str, Any]) -> None:
        payload = bridge_packet.get("payload")
        if not isinstance(payload, dict):
            return

        event = str(payload.get("event", "")).strip()
        session_id = str(payload.get("session_id", "")).strip()
        stream_id = str(payload.get("stream_id", "")).strip()
        turn_id = _safe_int(payload.get("turn_id"), default=0)
        if not event or not session_id or not stream_id or turn_id <= 0:
            return
        if self.args.session_id and session_id != self.args.session_id:
            return
        if self.args.stream_id and stream_id != self.args.stream_id:
            return

        key = _turn_key(session_id, stream_id, turn_id)
        state = self.turns.get(key)
        if state is None:
            state = TurnState(session_id=session_id, stream_id=stream_id, turn_id=turn_id)
            self.turns[key] = state

        state.events.append(event)
        state.emotion_style = payload.get("emotion_style") or state.emotion_style

        if event == "turn_start":
            state.turn_start_seen = True
        elif event == "audio_ready":
            state.audio_ready_seen = True
            if isinstance(bridge_packet.get("audio"), dict):
                state.audio = dict(bridge_packet["audio"])
            elif isinstance(payload.get("audio"), dict):
                state.audio = dict(payload["audio"])
        elif event == "motion_plan":
            state.motion_plan_seen = True
            state.viseme_seq = self._as_list(payload.get("viseme_seq"))
            state.expression_seq = self._as_list(payload.get("expression_seq"))
            state.motion_seq = self._as_list(payload.get("motion_seq"))
        elif event == "turn_end":
            state.turn_end_seen = True
        elif event in {"turn_error", "turn_abort"}:
            state.invalid_reason = event
            self._flush_state(state)
            self.turns.pop(key, None)
            return

        self._enforce_order_if_needed(state)
        print(
            f"[adapter] event={event} session={session_id} stream={stream_id} turn={turn_id}",
            flush=True,
        )

        if state.turn_end_seen:
            self._flush_state(state)
            self.turns.pop(key, None)

    @staticmethod
    def _as_list(value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []
        output: list[dict[str, Any]] = []
        for item in value:
            if isinstance(item, dict):
                output.append(item)
        return output

    def _enforce_order_if_needed(self, state: TurnState) -> None:
        if not self.args.strict_order:
            return
        expected = ["turn_start", "audio_ready", "motion_plan", "turn_end"]
        positions: dict[str, int] = {}
        for idx, event in enumerate(state.events):
            if event not in positions:
                positions[event] = idx
        for prev, cur in zip(expected, expected[1:]):
            if prev in positions and cur in positions and positions[prev] > positions[cur]:
                state.invalid_reason = f"event_order_invalid:{prev}>{cur}"
                break

    def _flush_state(self, state: TurnState) -> None:
        turn_dir = self.output_dir / state.session_id / state.stream_id / str(state.turn_id)
        turn_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_local_audio_path(state, turn_dir)

        bundle = {
            "contract_version": "a2f-ab-v1",
            "generated_at_ms": int(time.time() * 1000),
            "session_id": state.session_id,
            "stream_id": state.stream_id,
            "turn_id": state.turn_id,
            "emotion_style": state.emotion_style,
            "events": state.events,
            "valid": state.invalid_reason is None,
            "invalid_reason": state.invalid_reason,
            "audio": state.audio,
            "viseme_seq": state.viseme_seq,
            "expression_seq": state.expression_seq,
            "motion_seq": state.motion_seq,
            "ue_tracks": self._build_ue_tracks(state),
            "a2f_tracks": self._build_a2f_tracks(state),
        }

        bundle_path = turn_dir / "runtime_bundle.json"
        bundle_path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
        self._write_latest_files(state, bundle)

        print(
            f"[adapter] bundle ready: {bundle_path} "
            f"(audio={bool(state.audio)}, motion_plan={state.motion_plan_seen})",
            flush=True,
        )

        if self.args.ue_http_target:
            try:
                _json_post(self.args.ue_http_target, bundle["ue_tracks"], self.args.http_timeout_seconds)
                print(f"[adapter] ue push ok: {self.args.ue_http_target}", flush=True)
            except Exception as exc:
                print(f"[adapter] ue push failed: {type(exc).__name__}: {exc}", flush=True)

        if self.args.a2f_http_target:
            try:
                _json_post(self.args.a2f_http_target, bundle["a2f_tracks"], self.args.http_timeout_seconds)
                print(f"[adapter] a2f push ok: {self.args.a2f_http_target}", flush=True)
            except Exception as exc:
                print(f"[adapter] a2f push failed: {type(exc).__name__}: {exc}", flush=True)

    def _write_latest_files(self, state: TurnState, bundle: dict[str, Any]) -> None:
        stream_dir = self.output_dir / state.session_id / state.stream_id
        stream_dir.mkdir(parents=True, exist_ok=True)

        latest_bundle_path = stream_dir / "latest_runtime_bundle.json"
        latest_bundle_path.write_text(
            json.dumps(bundle, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        latest_ue_path = stream_dir / "latest_ue_tracks.json"
        latest_ue_path.write_text(
            json.dumps(bundle.get("ue_tracks", {}), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        latest_turn_path = stream_dir / "latest_turn_id.txt"
        latest_turn_path.write_text(str(state.turn_id), encoding="utf-8")

    def _ensure_local_audio_path(self, state: TurnState, turn_dir: Path) -> None:
        if not isinstance(state.audio, dict):
            state.audio = {}
        if state.audio.get("local_path"):
            return

        audio_url = state.audio.get("audio_url")
        if not isinstance(audio_url, str):
            return

        if audio_url.startswith("data:"):
            parts = audio_url.split(",", 1)
            if len(parts) != 2:
                return
            meta = parts[0].lower()
            if ";base64" not in meta:
                return
            try:
                audio_bytes = base64.b64decode(parts[1])
            except Exception:
                return
            suffix = ".wav"
            if "audio/mp3" in meta:
                suffix = ".mp3"
            elif "audio/ogg" in meta:
                suffix = ".ogg"
            audio_path = turn_dir / f"turn-{state.turn_id}{suffix}"
            audio_path.write_bytes(audio_bytes)
            state.audio["local_path"] = str(audio_path)
            state.audio.setdefault("source", "adapter_data_url")
            return

        # Keep remote URL as fallback when payload is not data URL.
        state.audio.setdefault("remote_url", audio_url)

    def _build_ue_tracks(self, state: TurnState) -> dict[str, Any]:
        viseme_to_curve = {
            "a": "Mouth_AA",
            "e": "Mouth_EH",
            "i": "Mouth_IH",
            "o": "Mouth_OH",
            "u": "Mouth_OO",
            "m": "Mouth_Closed",
            "sil": "Mouth_Closed",
        }
        # Empirical gains to make lip motion more visible in UE runtime.
        viseme_gain = {
            "a": 0.94,
            "e": 0.87,
            "i": 0.78,
            "o": 0.92,
            "u": 0.94,
            "m": 0.70,
            "sil": 0.36,
        }
        viseme_curves = []
        for item in state.viseme_seq:
            label = str(item.get("label", "sil")).lower()
            raw_weight = _safe_float(item.get("weight", 0.5), 0.5)
            scaled_weight = raw_weight * viseme_gain.get(label, 0.94)
            if label in {"m", "sil"}:
                scaled_weight = _clamp(scaled_weight, 0.0, 0.50)
            else:
                # Keep a small floor so lip movement is perceivable.
                scaled_weight = max(scaled_weight, 0.08)
                scaled_weight = min(scaled_weight, 0.60)
            viseme_curves.append(
                {
                    "start_ms": _safe_int(item.get("start_ms"), 0),
                    "end_ms": _safe_int(item.get("end_ms"), 0),
                    "curve": viseme_to_curve.get(label, "Mouth_Closed"),
                    "weight": _clamp(scaled_weight, 0.0, 1.0),
                }
            )

        body_actions = []
        for item in state.motion_seq:
            body_actions.append(
                {
                    "start_ms": _safe_int(item.get("start_ms"), 0),
                    "end_ms": _safe_int(item.get("end_ms"), 0),
                    "action": str(item.get("motion", "idle")),
                    "intensity": float(item.get("intensity", 0.5)),
                }
            )

        return {
            "session_id": state.session_id,
            "stream_id": state.stream_id,
            "turn_id": state.turn_id,
            # Prefer per-turn concrete file to avoid stale playback when latest.wav is locked on Windows.
            "audio_path": state.audio.get("local_path") or state.audio.get("latest_local_path"),
            "audio_remote_url": state.audio.get("remote_url"),
            "emotion_style": state.emotion_style,
            "viseme_curves": viseme_curves,
            "expressions": state.expression_seq,
            "body_actions": body_actions,
        }

    def _build_a2f_tracks(self, state: TurnState) -> dict[str, Any]:
        # This payload shape is intentionally generic; B-side can map it to
        # specific A2F REST/LiveLink APIs without changing the upstream contract.
        return {
            "session_id": state.session_id,
            "stream_id": state.stream_id,
            "turn_id": state.turn_id,
            "audio_path": state.audio.get("local_path"),
            "audio_remote_url": state.audio.get("remote_url"),
            "sample_rate_hz": state.audio.get("sample_rate_hz"),
            "duration_ms": state.audio.get("duration_ms"),
            "viseme_seq": state.viseme_seq,
            "expression_seq": state.expression_seq,
            "motion_seq": state.motion_seq,
        }


def main() -> int:
    args = parse_args()
    adapter = RuntimeAdapter(args)
    try:
        return adapter.run()
    except KeyboardInterrupt:
        print("\n[adapter] interrupted", flush=True)
        return 0
    except Exception as exc:
        print(f"[adapter] fatal: {type(exc).__name__}: {exc}", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
