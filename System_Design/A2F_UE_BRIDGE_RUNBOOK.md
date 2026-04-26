# A2F / UE Bridge Runbook

Goal: consume `audio_ready + motion_plan` and drive talking + upper-body actions.

This runbook uses two scripts:

- `a22_demo/avatar_ws_bridge.py` (A side, pulls from avatar-service WS)
- `a22_demo/ue_a2f_runtime_adapter.py` (B side adapter, consumes UDP and builds runtime bundle)

## 1) Terminal A: start avatar-service

```bash
cd /root/autodl-tmp/a22/code/FuChuangSai_A22/remote/avatar-service
source /root/autodl-tmp/a22/.uv_envs/avatar-service/bin/activate
set -a; source .env; set +a
uv run --active uvicorn app:app --host 127.0.0.1 --port 19300
```

Health check:

```bash
curl -s http://127.0.0.1:19300/health
```

## 2) Terminal B: start WS bridge (A output -> UDP)

```bash
cd /root/autodl-tmp/a22/code/FuChuangSai_A22
source /root/autodl-tmp/a22/.uv_envs/avatar-service/bin/activate

python a22_demo/avatar_ws_bridge.py \
  --ws-url ws://127.0.0.1:19300/ws/avatar \
  --session-id demo_s1 \
  --stream-id demo_stream_1 \
  --output-dir /root/autodl-tmp/a22/tmp/avatar_bridge \
  --avatar-base-url http://127.0.0.1:19300 \
  --udp-host 127.0.0.1 \
  --udp-port 19310
```

## 3) Terminal C: start runtime adapter (UDP -> UE/A2F bundle)

```bash
cd /root/autodl-tmp/a22/code/FuChuangSai_A22
source /root/autodl-tmp/a22/.uv_envs/avatar-service/bin/activate

python a22_demo/ue_a2f_runtime_adapter.py \
  --listen-host 127.0.0.1 \
  --listen-port 19310 \
  --output-dir /root/autodl-tmp/a22/tmp/ue_a2f_runtime \
  --session-id demo_s1 \
  --stream-id demo_stream_1 \
  --strict-order
```

Optional forwarding:

- add `--ue-http-target http://127.0.0.1:19400/ue/turn`
- add `--a2f-http-target http://127.0.0.1:19500/a2f/turn`

## 4) Trigger one turn

```bash
curl -s http://127.0.0.1:19300/generate \
  -H "Content-Type: application/json" \
  -d '{
    "session_id":"demo_s1",
    "turn_id":101,
    "reply_text":"hello, this is a2f and ue integration test.",
    "emotion_style":"supportive",
    "avatar_action":{"facial_expression":"smile","head_motion":"nod"},
    "turn_time_window":{"stream_id":"demo_stream_1"}
  }'
```

Expected event order:

1. `turn_start`
2. `audio_ready`
3. `motion_plan`
4. `turn_end`

## 5) Output artifacts

Bridge logs:

- `/root/autodl-tmp/a22/tmp/avatar_bridge/demo_s1/demo_stream_1/events-*.jsonl`

Runtime bundle:

- `/root/autodl-tmp/a22/tmp/ue_a2f_runtime/demo_s1/demo_stream_1/101/runtime_bundle.json`

The bundle includes:

- identity: `session_id + stream_id + turn_id`
- `audio.local_path` (or remote url fallback)
- `viseme_seq`, `expression_seq`, `motion_seq`
- normalized `ue_tracks` and `a2f_tracks`

## 6) B-side integration rule

UE/A2F renderer must:

1. filter by exact `session_id + stream_id + turn_id`
2. start audio using `audio.local_path` on `audio_ready`
3. schedule all cues by relative milliseconds from audio start (`t=0`)
4. close runtime state on `turn_end`

## 7) Troubleshooting

If no audio in bundle:

1. check `/generate` response has `reply_audio_url`
2. inspect bridge jsonl logs for `audio_ready`
3. verify `--avatar-base-url` can reach `/media/audio/...`

If bundle missing motion:

1. inspect bridge logs for `motion_plan`
2. verify `stream_id` matches between subscribe and generate request

If order invalid under `--strict-order`:

1. confirm only one producer writes one turn id
2. verify no duplicate out-of-order resend in upstream service
