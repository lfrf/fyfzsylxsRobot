#!/usr/bin/env python3
import argparse
import json
import time
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Follow the latest edge-backend events and bridge logs with compact status output."
    )
    parser.add_argument(
        "--log-dir",
        default="/home/siyuen/docker_ws/A22/logs/edge-backend",
        help="Directory containing edge-backend log files.",
    )
    parser.add_argument(
        "--from-start",
        action="store_true",
        help="Read the latest log files from the beginning instead of following only new records.",
    )
    return parser.parse_args()


def find_latest_trace(log_dir: Path, pattern: str) -> Path | None:
    candidates = sorted(log_dir.glob(pattern), key=lambda path: path.stat().st_mtime)
    if not candidates:
        return None
    return candidates[-1]


def summarize_record(record: dict) -> list[str]:
    event_type = record.get("event_type", "-")
    payload = record.get("payload", {})
    request_id = payload.get("request_id", "-")
    ts = record.get("ts", "-")

    lines = [f"[{ts}] {event_type}  request={request_id}"]

    if event_type == "chat_request_received":
        lines.append(
            "  "
            f"mode={payload.get('input_type', '-')} "
            f"session={payload.get('session_id', '-')} "
            f"turn={payload.get('turn_id', '-')} "
            f"has_audio={payload.get('has_audio', '-')}"
        )
    elif event_type == "asr_warmup_start":
        lines.append(
            "  "
            f"provider={payload.get('provider', '-')} "
            f"device={payload.get('device', '-')} "
            f"model={payload.get('model_ref', '-')}"
        )
    elif event_type == "asr_warmup_ready":
        lines.append(
            "  "
            f"provider={payload.get('provider', '-')} "
            f"latency_ms={payload.get('latency_ms', '-')} "
            f"text={payload.get('recognized_text', '')!r}"
        )
    elif event_type == "asr_warmup_error":
        lines.append(
            "  "
            f"provider={payload.get('provider', '-')} "
            f"error={payload.get('error_type', '-')}: {payload.get('detail', '-')}"
        )
    elif event_type == "asr_transcription":
        lines.append(
            "  "
            f"provider={payload.get('provider', '-')} "
            f"source={payload.get('source', '-')} "
            f"latency_ms={payload.get('latency_ms', '-')} "
            f"fallback={payload.get('fallback_used', '-')}"
        )
        lines.append(f"  recognized_text={payload.get('recognized_text', '')!r}")
        client_hint = payload.get("client_asr_text")
        if client_hint:
            lines.append(f"  client_asr_text={client_hint!r}")
    elif event_type == "chat_request_prepared":
        lines.append(
            "  "
            f"text_source={payload.get('text_source', '-')} "
            f"alignment={payload.get('alignment_mode', '-')} "
            f"resolved_user_text={payload.get('resolved_user_text', '')!r}"
        )
    elif event_type == "bridge_outbound":
        bridge_payload = payload.get("payload", {})
        lines.append(
            "  "
            f"to_remote={payload.get('url', '-')} "
            f"mode={bridge_payload.get('input_type', '-')} "
            f"text_source={bridge_payload.get('text_source', '-')}"
        )
        lines.append(f"  forwarded_text={bridge_payload.get('user_text', '')!r}")
    elif event_type == "bridge_inbound":
        response_payload = payload.get("payload", {})
        lines.append(
            "  "
            f"status={payload.get('status_code', '-')} "
            f"latency_ms={payload.get('latency_ms', '-')} "
            f"reply={response_payload.get('reply_text', '')!r}"
        )
    elif event_type in {"bridge_error", "chat_error"}:
        lines.append(
            "  "
            f"status={payload.get('status_code', '-')} "
            f"latency_ms={payload.get('latency_ms', '-')} "
            f"detail={payload.get('detail', '-')}"
        )
    elif event_type == "chat_response":
        lines.append(
            "  "
            f"server_status={payload.get('server_status', '-')} "
            f"source={payload.get('response_source', '-')} "
            f"reply={payload.get('reply_text_preview', '')!r}"
        )
    else:
        compact = {key: value for key, value in payload.items() if key != "audio_base64"}
        lines.append(f"  payload={json.dumps(compact, ensure_ascii=False)}")

    return lines


def follow_latest(log_dir: Path, patterns: list[str], from_start: bool) -> None:
    current_files: dict[str, Path | None] = {pattern: None for pattern in patterns}
    handles: dict[str, object] = {}

    while True:
        for pattern in patterns:
            latest_trace = find_latest_trace(log_dir, pattern)
            if latest_trace is None:
                continue

            if current_files[pattern] != latest_trace:
                previous_handle = handles.pop(pattern, None)
                if previous_handle:
                    previous_handle.close()
                current_files[pattern] = latest_trace
                handle = latest_trace.open("r", encoding="utf-8")
                if not from_start:
                    handle.seek(0, 2)
                handles[pattern] = handle

            handle = handles.get(pattern)
            if not handle:
                continue

            line = handle.readline()
            if not line:
                continue

            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue

            print()
            print("=" * 96)
            for output_line in summarize_record(record):
                print(output_line)

        time.sleep(0.2)


def main() -> None:
    args = parse_args()
    log_dir = Path(args.log_dir).expanduser()
    log_dir.mkdir(parents=True, exist_ok=True)
    follow_latest(
        log_dir=log_dir,
        patterns=[
            "edge-backend-events-*.jsonl",
            "edge-backend-bridge-*.jsonl",
        ],
        from_start=args.from_start,
    )


if __name__ == "__main__":
    main()
