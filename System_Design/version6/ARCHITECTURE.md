# Version6 Architecture

## Model, Weight, Cache Paths

This section is the authoritative path record for the current and planned system.

### Remote model root

```text
/data/zifeng/siyuan/A22/models
```

### Current confirmed model paths

```text
Qwen LLM:
/data/zifeng/siyuan/A22/models/Qwen2.5-7B-Instruct

BELLE Whisper ASR:
/data/zifeng/siyuan/A22/models/Belle-whisper-large-v3-turbo-zh
```

### Planned model placement

```text
Vision model:
/data/zifeng/siyuan/A22/models/<vision-model-name>

Avatar / digital-human model:
/data/zifeng/siyuan/A22/models/<avatar-model-name>

TTS model:
/data/zifeng/siyuan/A22/models/<tts-model-name>
```

### Cache and temporary files

All runtime cache, uploaded media, extracted features, and generated avatar assets should be stored under:

```text
/data/zifeng/siyuan/A22/tmp
```

Recommended layout:

```text
/data/zifeng/siyuan/A22/tmp
├─ ingest/
│  └─ <session_id>/<turn_id>/
├─ features/
│  └─ <session_id>/<turn_id>/
├─ avatar/
│  └─ <session_id>/<turn_id>/
├─ tts/
│  └─ <session_id>/<turn_id>/
└─ logs/
```

### GPU allocation plan

Recommended first production-like split:

```text
GPU0: qwen-server
GPU1: speech-service + vision-service
GPU2: avatar-service
```

Current fallback split if one card is intentionally reserved:

```text
GPU0: qwen-server
GPU1: speech-service + avatar-service
GPU2: reserved
```

## Current baseline

The current baseline already supports:

- local frontend text input
- local frontend audio input
- local BELLE ASR
- local edge-backend normalization
- SSH tunnel forwarding
- remote orchestrator
- remote qwen-server
- remote LLM reply rendered in frontend

## Target architecture

The target system should evolve from the current local-ASR architecture to the following service split:

```text
local/
├─ frontend
└─ edge-backend

remote/
├─ qwen-server
├─ speech-service
├─ vision-service
├─ avatar-service
└─ orchestrator
```

Responsibilities:

- `local/frontend`: capture text, audio, and video; render the avatar
- `local/edge-backend`: session control, turn packaging, light preprocessing, SSH forwarding
- `remote/speech-service`: ASR and speech-side feature extraction
- `remote/vision-service`: video/frame preprocessing and visual feature extraction
- `remote/orchestrator`: multimodal alignment, context management, policy, LLM orchestration
- `remote/avatar-service`: TTS, viseme generation, expression generation, motion generation
- `remote/qwen-server`: OpenAI-compatible LLM serving

## Plan

### Stage 1: Shared protocol stabilization

Goals:

- define `turn_time_window`
- define `avatar_output` contract
- reserve WebSocket-compatible fields
- keep current HTTP turn-based flow working

Status:

- implemented in this version

### Stage 2: Video ingest on local

Goals:

- add browser camera capture
- collect key frames or short clips per turn
- attach time-aligned metadata
- upload compact media payloads instead of raw full-rate stream

Planned new local files:

```text
local/frontend/src/video/cameraTurnRecorder.js
local/frontend/src/video/frameSampler.js
local/frontend/src/video/frameEncoder.js
local/frontend/src/ui/CameraPanel.js
local/edge-backend/services/media/video_turn_service.py
local/edge-backend/services/media/frame_selector.py
local/edge-backend/services/media/media_package_builder.py
local/edge-backend/services/remote_media_client.py
```

### Stage 3: Move ASR to remote

Goals:

- disable heavy ASR inference on local by default
- upload audio to remote `speech-service`
- extract transcript + speech features remotely

Planned new remote files:

```text
remote/speech-service/app.py
remote/speech-service/config.py
remote/speech-service/models.py
remote/speech-service/routes/transcribe.py
remote/speech-service/services/asr_runtime.py
remote/speech-service/services/feature_extractor.py
```

### Stage 4: Vision service and multimodal alignment

Goals:

- process only video inputs in `vision-service`
- convert video to structured `vision_features`
- align `video + text` or `video + audio` in `alignment-service`

Planned new remote files:

```text
remote/vision-service/app.py
remote/vision-service/config.py
remote/vision-service/models.py
remote/vision-service/routes/extract.py
remote/vision-service/services/frame_feature_extractor.py
remote/orchestrator/services/alignment/video_audio_alignment.py
remote/orchestrator/services/alignment/video_text_alignment.py
```

### Stage 5: Avatar generation

Goals:

- receive LLM text and style outputs
- generate TTS, viseme sequence, expression sequence, motion sequence
- send parameterized output back to frontend renderer

Planned new remote files:

```text
remote/avatar-service/app.py
remote/avatar-service/config.py
remote/avatar-service/models.py
remote/avatar-service/routes/generate.py
remote/avatar-service/services/tts_runtime.py
remote/avatar-service/services/viseme_generator.py
remote/avatar-service/services/expression_generator.py
remote/avatar-service/services/motion_generator.py
```

### Stage 6: Transport upgrade

Goals:

- keep the current HTTP turn-based API
- reserve fields for future WebSocket migration
- later migrate avatar playback and media streaming to WebSocket

## Turn Time Window

`turn_time_window` is the canonical per-turn timing envelope used to align text, audio, and video.

Current schema fields:

```text
window_id
source_clock
transport_mode
stream_id
sequence_id
capture_started_at_ms
capture_ended_at_ms
audio_started_at_ms
audio_ended_at_ms
video_started_at_ms
video_ended_at_ms
window_duration_ms
```

### Definition

- `capture_started_at_ms`: when the client started collecting this turn
- `capture_ended_at_ms`: when the client ended collecting this turn
- `audio_started_at_ms` / `audio_ended_at_ms`: audio segment boundaries
- `video_started_at_ms` / `video_ended_at_ms`: video segment boundaries
- `window_duration_ms`: overall turn duration
- `transport_mode`: currently `http_turn`, reserved for future `websocket_stream`
- `stream_id` and `sequence_id`: reserved for future real-time streaming sessions

### Current implementation

- audio turns now include a real browser-side window
- text turns now include a minimal synthetic turn window for protocol consistency

## Avatar Output Contract

`avatar_output` is the future-facing structured contract between remote generation services and the frontend avatar renderer.

Current schema fields:

```text
contract_version
renderer_mode
transport_mode
websocket_endpoint
stream_id
sequence_id
avatar_id
emotion_style
audio
viseme_seq
expression_seq
motion_seq
```

### Design intent

- `audio`: TTS output reference
- `viseme_seq`: mouth / lip-sync timeline
- `expression_seq`: facial expression timeline
- `motion_seq`: head or body motion timeline
- `websocket_endpoint` and `stream_id`: reserved for future streaming render mode

### Current implementation

- remote orchestrator now returns `avatar_output`
- the contract currently contains placeholder parameterized cues derived from the existing policy layer
- the existing `emotion_style` and `avatar_action` fields are preserved for backward compatibility

## Current code changes in version6

### Shared

Updated files:

```text
shared/contracts/schemas.py
shared/contracts/api_v1.md
shared/contracts/chat_request.example.json
shared/contracts/chat_response.example.json
```

Implemented:

- `TurnTimeWindowSchema`
- `AvatarAudioCueSchema`
- `VisemeCueSchema`
- `ExpressionCueSchema`
- `MotionCueSchema`
- `AvatarOutputSchema`
- response/request examples updated

### Local

Updated files:

```text
local/frontend/src/audio/audioTurnRecorder.js
local/frontend/src/main.js
local/edge-backend/models.py
local/edge-backend/routes/chat.py
local/edge-backend/services/input_preprocessor.py
```

Implemented:

- real browser-side turn window for audio input
- minimal turn window for text input
- turn window propagation from frontend to edge-backend to remote
- new request logging for turn window presence

### Remote

Updated files:

```text
remote/orchestrator/models.py
remote/orchestrator/services/policy_service.py
remote/orchestrator/services/dialog_service.py
```

Implemented:

- `avatar_output` generation in orchestrator
- placeholder viseme/expression/motion sequences
- response echo of `turn_time_window`

## Real-time migration note

The current architecture remains HTTP turn-based, but the contract now explicitly reserves the following WebSocket-related fields:

- `turn_time_window.transport_mode`
- `turn_time_window.stream_id`
- `turn_time_window.sequence_id`
- `avatar_output.transport_mode`
- `avatar_output.websocket_endpoint`
- `avatar_output.stream_id`
- `avatar_output.sequence_id`

This means a future server migration can keep the current semantic structure while replacing the transport layer with:

- WebSocket for avatar playback
- WebSocket or gRPC for continuous media streaming
- remote media services on stronger hardware

## What still needs to be built

The remaining major tasks are:

1. local video capture and compact media packaging
2. remote `speech-service`
3. remote `vision-service`
4. remote `avatar-service`
5. alignment logic for `video + audio` and `video + text`
6. frontend avatar renderer upgrade from placeholder to real runtime consumer
