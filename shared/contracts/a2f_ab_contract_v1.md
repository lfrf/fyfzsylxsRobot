# A2F A/B Integration Contract v1

Version: `a2f-ab-v1`  
Status: frozen for current sprint (breaking changes require `v2`)

## 1. Scope

This contract defines the interface between:

- A: server side (`orchestrator` + `avatar-service` + A2F runtime)
- B: renderer side (Unreal/Unity + upper-body avatar)

Goal: support near-real-time 3D digital human playback with stable turn alignment.

## 2. Single Source of Truth

The following fields already exist in current repo schemas and must be reused:

- `session_id`
- `turn_id`
- `turn_time_window.stream_id`
- `avatar_output.audio`
- `avatar_output.viseme_seq`
- `avatar_output.expression_seq`
- `avatar_output.motion_seq`
- `avatar_output.emotion_style`

Reference schema file:

- `shared/contracts/schemas.py`

## 3. Turn Identity and Alignment (must follow)

Each playable unit is uniquely identified by:

- `session_id` + `turn_id` + `stream_id`

Rules:

1. `session_id` is stable for one user conversation.
2. `turn_id` increases by 1 in the same session.
3. `stream_id` identifies one playback stream/channel for that session.
4. B must drop any event whose identity does not match current active turn.

## 4. Timeline Semantics (must follow)

All animation timing fields use:

- unit: milliseconds
- zero point: `audio_start_ms = 0` of the current turn

Rules:

1. `viseme_seq/expression_seq/motion_seq` are relative to current turn audio start.
2. If absolute time is needed for logs, use an extra field `server_ts_ms` only for diagnostics.
3. B schedules cues strictly by relative time; do not infer from network receive time.

## 5. Transport Contract

Default mode: WebSocket push from A to B.

Fallback mode: HTTP poll (for demos only).

WebSocket endpoint recommendation:

- `/ws/avatar`

Event ordering for one turn (required):

1. `turn_start`
2. `audio_ready`
3. zero or more `facial_frame` (optional in current phase)
4. `motion_plan`
5. `turn_end`

Error/abort path:

1. `turn_error` (recoverable)
2. `turn_abort` (non-recoverable)

## 6. Event Payloads

## 6.1 `turn_start`

Purpose: open turn context on renderer.

Required fields:

- `event`: `"turn_start"`
- `contract_version`: `"a2f-ab-v1"`
- `session_id`: string
- `turn_id`: integer >= 1
- `stream_id`: string
- `emotion_style`: string
- `renderer_mode`: string (suggested `realtime_3d`)

## 6.2 `audio_ready`

Purpose: provide playable audio.

Required fields:

- `event`: `"audio_ready"`
- `session_id`, `turn_id`, `stream_id`
- `audio`: object
- `audio.audio_url` OR `audio.audio_base64`
- `audio.mime_type` (example `audio/wav`)
- `audio.duration_ms`
- `audio.sample_rate_hz` (optional but strongly recommended)

Rule:

- at least one of `audio_url` or `audio_base64` must exist.

## 6.3 `motion_plan`

Purpose: provide body and face cue sequences for the whole turn.

Required fields:

- `event`: `"motion_plan"`
- `session_id`, `turn_id`, `stream_id`
- `viseme_seq`: list
- `expression_seq`: list
- `motion_seq`: list

Sequence item constraints:

- `start_ms >= 0`
- `end_ms >= start_ms`
- intensity/weight in range `[0,1]` when provided

## 6.4 `facial_frame` (optional phase-2)

Purpose: per-frame A2F output stream for finer lip sync.

Required fields:

- `event`: `"facial_frame"`
- `session_id`, `turn_id`, `stream_id`
- `frame_index`
- `timestamp_ms`
- `blendshape_weights`: key-value map

Current sprint can skip this event and rely on `viseme_seq`.

## 6.5 `turn_end`

Purpose: close turn, allow cleanup.

Required fields:

- `event`: `"turn_end"`
- `session_id`, `turn_id`, `stream_id`
- `status`: `"ok"`

## 6.6 `turn_error`

Purpose: report recoverable issue while keeping stream alive.

Required fields:

- `event`: `"turn_error"`
- `session_id`, `turn_id`, `stream_id`
- `error_code`
- `error_message`

## 7. Error Codes

Reserved codes:

- `A2F_UNAVAILABLE`: A2F runtime not reachable
- `AUDIO_MISSING`: audio not generated
- `AUDIO_FORMAT_UNSUPPORTED`: renderer cannot decode audio
- `MOTION_SCHEMA_INVALID`: sequence validation failed
- `TURN_IDENTITY_MISMATCH`: session/turn/stream mismatch
- `RENDERER_TIMEOUT`: renderer ack timeout

## 8. A/B Responsibility Boundary

A owns:

- generation and delivery of audio + cue payloads
- schema validation before send
- monotonic `turn_id`
- stable error signaling

B owns:

- loading avatar asset with face blendshapes and upper-body skeleton
- applying viseme/expression/motion by timeline
- rejecting identity-mismatch packets
- reporting runtime ack/error

## 9. Minimum ACK Contract

B -> A should return (WebSocket or HTTP callback):

- `ack_type`: `turn_start_ack` | `audio_ready_ack` | `motion_plan_ack` | `turn_end_ack`
- `session_id`, `turn_id`, `stream_id`
- `ok`: boolean
- `detail`: optional

## 10. Acceptance Criteria (DoD)

This contract is considered done when:

1. A can emit `turn_start -> audio_ready -> motion_plan -> turn_end` for 10 consecutive turns.
2. B can render upper-body avatar without turn mix-up.
3. No schema validation error in 10-turn run.
4. Median first-motion latency <= 1500 ms (from turn request to first visible motion).
5. All logs include `session_id + turn_id + stream_id`.

## 11. Change Policy

If any field shape changes:

1. create `a2f_ab_contract_v2.md`
2. keep v1 compatibility for at least one demo cycle
3. do not hot-change v1 payload in place

