# RobotMatch API contract v1

Version: **robot-v1**.

## Scope

This contract describes the JSON shape between Raspberry Pi `raspirobot` and remote `orchestrator`.

The active robot runtime uses:

```text
raspirobot -> remote/orchestrator
```

Old frontend, edge-backend, avatar, lip-sync, viseme, and video-avatar routes are not part of the active robot path.

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health` | Liveness and minimal status. |
| POST | `/v1/robot/chat_turn` | One robot voice turn in, structured robot reply out. |

## Request: `POST /v1/robot/chat_turn`

Content-Type: `application/json`

Required request shape:

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `session_id` | string | yes | Stable robot session id. |
| `turn_id` | string | yes | Turn id such as `turn-0001`. |
| `mode` | string | yes | Current session mode hint: `care`, `accompany`, `learning`, or `game`. Legacy aliases are normalized server-side. |
| `input` | object | yes | `RobotInput`, including `audio_base64`. |
| `vision_context` | object | no | Mock or future real face/vision context. |
| `robot_state` | object | no | Local state and hardware readiness. |
| `request_options` | object | no | Optional TTS/action hints. |

`RobotInput`:

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `type` | string | yes | `audio_base64` for V1. |
| `audio_base64` | string | yes | Base64 wav payload. |
| `audio_format` | string | no | Usually `wav`. |
| `sample_rate` | integer | no | Usually `16000`. |
| `channels` | integer | no | Usually `1`. |
| `duration_ms` | integer | no | Audio duration. |
| `text_hint` | string | no | Stub ASR text for tests only. |

See `chat_request.example.json`.

## Response: `RobotChatResponse`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `success` | boolean | yes | Whether the turn succeeded. |
| `session_id` | string | yes | Echoed session id. |
| `turn_id` | string | yes | Echoed turn id. |
| `mode` | object | yes | Active `ModeInfo`. |
| `mode_switch` | object | no | Mode switching result. |
| `mode_changed` | boolean | yes | True when this turn changed session mode. |
| `active_rag_namespace` | string | no | RAG namespace selected for this turn. |
| `asr_text` | string | yes | Recognized or stubbed user text. |
| `reply_text` | string | yes | Robot speech text. |
| `emotion` | object | yes | Emotion result. |
| `tts` | object | yes | De-avatarized TTS result. |
| `robot_action` | object | yes | Semantic robot expression/motion action. |
| `error` | object | no | Error details if failed. |
| `fallback` | object | no | Safe fallback details if needed. |
| `debug` | object | no | Lightweight diagnostics. |

Robot TTS result:

```json
{
  "type": "audio_url",
  "audio_url": "mock://tts/demo-session-001/turn-0001.wav",
  "format": "wav"
}
```

Robot action result:

```json
{
  "expression": "comfort",
  "motion": "slow_nod",
  "speech_style": "care_gentle"
}
```

The robot path must not return:

```text
avatar_output
avatar_action
viseme
lip_sync
video_url
reply_video_url
reply_video_stream_url
```

See `chat_response.example.json`.

## Mode Switching

Mode switching is session-based.

Supported commands include:

```text
切换为关怀模式 / 进入关怀模式
切换为陪伴模式 / 进入陪伴模式
切换为学习模式 / 进入学习模式
切换为游戏模式 / 进入游戏模式
```

Mode mapping:

| Mode | RAG namespace | Speech style |
| --- | --- | --- |
| `care` | `care` | `care_gentle` |
| `accompany` | `general` | `natural_warm` |
| `learning` | `learning` | `learning_focused` |
| `game` | `game` | `game_playful` |

Legacy aliases are accepted for compatibility but never returned as active mode IDs:

```text
elderly -> care
normal -> accompany
student -> learning
child -> game
```
