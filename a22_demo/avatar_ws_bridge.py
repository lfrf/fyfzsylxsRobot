#!/usr/bin/env python3
"""
Avatar WS Bridge

Consume avatar-service /ws/avatar events and forward them to downstream runtimes
(Unreal/Unity receiver, A2F adapter, or any HTTP endpoint).

Key capabilities:
- Subscribe to one (session_id, stream_id) on /ws/avatar
- Persist data:audio/wav;base64 payloads from audio_ready to local files
- Emit normalized JSON packets over UDP and/or HTTP
- Append all forwarded packets to local jsonl audit logs
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import mimetypes
import shutil
import socket
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urljoin
from urllib.request import Request, urlopen

try:
    import websockets
except Exception:  # pragma: no cover - dependency missing at runtime
    websockets = None  # type: ignore[assignment]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bridge /ws/avatar events to UE/A2F receivers.")
    parser.add_argument(
        "--ws-url",
        default="ws://127.0.0.1:19300/ws/avatar",
        help="Avatar websocket endpoint.",
    )
    parser.add_argument(
        "--session-id",
        required=True,
        help="Session id to subscribe.",
    )
    parser.add_argument(
        "--stream-id",
        required=True,
        help="Stream id to subscribe.",
    )
    parser.add_argument(
        "--output-dir",
        default="/root/autodl-tmp/a22/tmp/avatar_bridge",
        help="Directory for persisted audio/events.",
    )
    parser.add_argument(
        "--avatar-base-url",
        default="http://127.0.0.1:19300",
        help="Base URL used to resolve relative audio URLs such as /media/audio/...",
    )
    parser.add_argument(
        "--udp-host",
        default="127.0.0.1",
        help="UDP target host for UE/A2F adapter. Set empty to disable UDP.",
    )
    parser.add_argument(
        "--udp-port",
        type=int,
        default=19310,
        help="UDP target port for UE/A2F adapter.",
    )
    parser.add_argument(
        "--http-target",
        default="",
        help="Optional downstream HTTP endpoint that receives bridged packets (POST JSON).",
    )
    parser.add_argument(
        "--http-timeout-seconds",
        type=float,
        default=3.0,
        help="Timeout for downstream HTTP push.",
    )
    parser.add_argument(
        "--no-audio-download",
        action="store_true",
        help="If set, do not download remote audio URLs; only persist data URLs.",
    )
    parser.add_argument(
        "--latest-audio-name",
        default="latest.wav",
        help=(
            "If non-empty, mirror each received audio payload to this stable filename under "
            "<output-dir>/<session>/<stream>/ for easier UE playback."
        ),
    )
    parser.add_argument(
        "--ping-interval-seconds",
        type=float,
        default=20.0,
        help="WebSocket ping interval.",
    )
    return parser.parse_args()


class AvatarWsBridge:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.output_dir = Path(args.output_dir).expanduser()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.session_dir = self.output_dir / args.session_id / args.stream_id
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.events_path = self.session_dir / f"events-{int(time.time())}.jsonl"
        self.latest_audio_path = (
            self.session_dir / args.latest_audio_name if args.latest_audio_name else None
        )
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    async def run(self) -> None:
        print(
            f"[bridge] connect ws={self.args.ws_url} session={self.args.session_id} "
            f"stream={self.args.stream_id}",
            flush=True,
        )
        async with websockets.connect(
            self.args.ws_url,
            ping_interval=self.args.ping_interval_seconds,
            max_size=20_000_000,
        ) as ws:
            await self._handle_handshake(ws)
            async for raw_message in ws:
                await self._handle_message(raw_message)

    async def _handle_handshake(self, ws: websockets.WebSocketClientProtocol) -> None:
        connected = await ws.recv()
        print(f"[bridge] connected: {connected}", flush=True)
        subscribe_payload = {
            "action": "subscribe",
            "session_id": self.args.session_id,
            "stream_id": self.args.stream_id,
        }
        await ws.send(json.dumps(subscribe_payload, ensure_ascii=False))
        subscribed = await ws.recv()
        print(f"[bridge] subscribed: {subscribed}", flush=True)

    async def _handle_message(self, raw_message: str) -> None:
        try:
            message = json.loads(raw_message)
        except json.JSONDecodeError:
            print(f"[bridge] skip non-json message: {raw_message[:120]}", flush=True)
            return

        event = str(message.get("event", ""))
        if not event:
            return

        packet = {
            "bridge_ts_ms": int(time.time() * 1000),
            "event": event,
            "session_id": message.get("session_id"),
            "turn_id": message.get("turn_id"),
            "stream_id": message.get("stream_id"),
            "payload": message,
        }

        if event == "audio_ready":
            audio_packet = self._process_audio_ready(message)
            if audio_packet:
                packet["audio"] = audio_packet

        self._append_event(packet)
        self._push_udp(packet)
        self._push_http(packet)
        print(
            f"[bridge] event={event} session={packet.get('session_id')} "
            f"turn={packet.get('turn_id')} stream={packet.get('stream_id')}",
            flush=True,
        )

    def _process_audio_ready(self, message: dict[str, Any]) -> dict[str, Any] | None:
        audio = message.get("audio")
        if not isinstance(audio, dict):
            return None

        audio_url = audio.get("audio_url")
        mime_type = audio.get("mime_type") or "audio/wav"
        if not audio_url:
            return None

        turn_id = message.get("turn_id", "unknown")
        suffix = self._suffix_for_mime(mime_type)
        local_audio_path = self.session_dir / f"turn-{turn_id}{suffix}"

        if isinstance(audio_url, str) and audio_url.startswith("data:"):
            payload = audio_url.split(",", 1)
            if len(payload) != 2:
                return None
            audio_bytes = base64.b64decode(payload[1])
            local_audio_path.write_bytes(audio_bytes)
            audio_packet = {
                "local_path": str(local_audio_path),
                "source": "data_url",
                "mime_type": mime_type,
                "duration_ms": audio.get("duration_ms"),
                "sample_rate_hz": audio.get("sample_rate_hz"),
            }
            self._mirror_latest_audio(local_audio_path, audio_packet)
            return audio_packet

        if self.args.no_audio_download:
            return {
                "remote_url": self._resolve_audio_url(str(audio_url)),
                "source": "remote_url_only",
                "mime_type": mime_type,
                "duration_ms": audio.get("duration_ms"),
                "sample_rate_hz": audio.get("sample_rate_hz"),
            }

        resolved_url = self._resolve_audio_url(str(audio_url))
        try:
            request = Request(resolved_url, method="GET")
            with urlopen(request, timeout=8) as response:
                audio_bytes = response.read()
            local_audio_path.write_bytes(audio_bytes)
            audio_packet = {
                "local_path": str(local_audio_path),
                "remote_url": resolved_url,
                "source": "downloaded_url",
                "mime_type": mime_type,
                "duration_ms": audio.get("duration_ms"),
                "sample_rate_hz": audio.get("sample_rate_hz"),
            }
            self._mirror_latest_audio(local_audio_path, audio_packet)
            return audio_packet
        except Exception as exc:  # pragma: no cover - runtime path
            return {
                "remote_url": resolved_url,
                "source": "download_failed",
                "error": f"{type(exc).__name__}: {exc}",
                "mime_type": mime_type,
                "duration_ms": audio.get("duration_ms"),
                "sample_rate_hz": audio.get("sample_rate_hz"),
            }

    def _mirror_latest_audio(self, local_audio_path: Path, audio_packet: dict[str, Any]) -> None:
        if self.latest_audio_path is None:
            return
        try:
            self.latest_audio_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(local_audio_path, self.latest_audio_path)
            audio_packet["latest_local_path"] = str(self.latest_audio_path)
        except Exception as exc:  # pragma: no cover - runtime path
            print(f"[bridge] latest audio mirror failed: {type(exc).__name__}: {exc}", flush=True)

    def _resolve_audio_url(self, value: str) -> str:
        if value.startswith("http://") or value.startswith("https://"):
            return value
        return urljoin(self.args.avatar_base_url.rstrip("/") + "/", value.lstrip("/"))

    @staticmethod
    def _suffix_for_mime(mime_type: str) -> str:
        guessed = mimetypes.guess_extension(mime_type.split(";")[0].strip())
        return guessed or ".wav"

    def _append_event(self, packet: dict[str, Any]) -> None:
        with self.events_path.open("a", encoding="utf-8") as fp:
            fp.write(json.dumps(packet, ensure_ascii=False) + "\n")

    def _push_udp(self, packet: dict[str, Any]) -> None:
        if not self.args.udp_host or self.args.udp_port <= 0:
            return
        try:
            udp_packet = self._to_udp_packet(packet)
            payload = json.dumps(udp_packet, ensure_ascii=False).encode("utf-8")
            self.udp_socket.sendto(payload, (self.args.udp_host, self.args.udp_port))
        except Exception as exc:  # pragma: no cover - runtime path
            print(f"[bridge] udp push failed: {type(exc).__name__}: {exc}", flush=True)

    def _push_http(self, packet: dict[str, Any]) -> None:
        if not self.args.http_target:
            return
        try:
            body = json.dumps(packet, ensure_ascii=False).encode("utf-8")
            req = Request(
                self.args.http_target,
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(req, timeout=self.args.http_timeout_seconds):
                pass
        except Exception as exc:  # pragma: no cover - runtime path
            print(f"[bridge] http push failed: {type(exc).__name__}: {exc}", flush=True)

    def _to_udp_packet(self, packet: dict[str, Any]) -> dict[str, Any]:
        event = str(packet.get("event", ""))
        payload = packet.get("payload")
        if not isinstance(payload, dict):
            payload = {}

        slim_payload: dict[str, Any] = {
            "event": payload.get("event"),
            "session_id": payload.get("session_id"),
            "turn_id": payload.get("turn_id"),
            "stream_id": payload.get("stream_id"),
        }

        if event == "turn_start":
            slim_payload["contract_version"] = payload.get("contract_version")
            slim_payload["emotion_style"] = payload.get("emotion_style")
            slim_payload["renderer_mode"] = payload.get("renderer_mode")
        elif event == "audio_ready":
            audio = payload.get("audio")
            if isinstance(audio, dict):
                slim_audio = dict(audio)
                audio_url = slim_audio.get("audio_url")
                if isinstance(audio_url, str) and audio_url.startswith("data:"):
                    # Remove inline base64 from UDP packets to keep payload under datagram limit.
                    slim_audio.pop("audio_url", None)
                    slim_audio["audio_url_inline"] = True
                slim_payload["audio"] = slim_audio
        elif event == "motion_plan":
            slim_payload["viseme_seq"] = payload.get("viseme_seq", [])
            slim_payload["expression_seq"] = payload.get("expression_seq", [])
            slim_payload["motion_seq"] = payload.get("motion_seq", [])
        elif event == "turn_end":
            slim_payload["status"] = payload.get("status")
        elif event in {"turn_error", "turn_abort"}:
            slim_payload["error_code"] = payload.get("error_code")
            slim_payload["error_message"] = payload.get("error_message")

        udp_packet = {
            "bridge_ts_ms": packet.get("bridge_ts_ms"),
            "event": event,
            "session_id": packet.get("session_id"),
            "turn_id": packet.get("turn_id"),
            "stream_id": packet.get("stream_id"),
            "payload": slim_payload,
        }
        if isinstance(packet.get("audio"), dict):
            udp_packet["audio"] = packet["audio"]
        return udp_packet


async def _main_async(args: argparse.Namespace) -> int:
    bridge = AvatarWsBridge(args)
    await bridge.run()
    return 0


def main() -> int:
    args = parse_args()
    try:
        if websockets is None:
            print(
                "[bridge] fatal: missing dependency 'websockets'. "
                "Install it in the running environment first.",
                flush=True,
            )
            return 2
        return asyncio.run(_main_async(args))
    except KeyboardInterrupt:
        print("\n[bridge] interrupted", flush=True)
        return 0
    except Exception as exc:
        print(f"[bridge] fatal: {type(exc).__name__}: {exc}", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
