# Version7 Architecture

## Path Registry

This section is the authoritative path record for model weights, runtime cache,
temporary files, and future service placement.

### Remote model root

```text
/data/zifeng/siyuan/A22/models
```

### Confirmed current model paths

```text
Qwen LLM
/data/zifeng/siyuan/A22/models/Qwen2.5-7B-Instruct

BELLE Whisper ASR
/data/zifeng/siyuan/A22/models/Belle-whisper-large-v3-turbo-zh
```

### Planned model placement

```text
Vision model
/data/zifeng/siyuan/A22/models/Qwen2.5-VL-7B-Instruct

2D avatar behavior model
/data/zifeng/siyuan/A22/models/<avatar-model-name>

TTS model
/data/zifeng/siyuan/A22/models/CosyVoice2-0.5B

CosyVoice runtime repository
/data/zifeng/siyuan/A22/models/CosyVoice
```

### Runtime cache and temporary files

All uploaded media, extracted features, generated audio, avatar cues, and
service-side temporary artifacts should be stored under:

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
├─ speech/
│  └─ <session_id>/<turn_id>/
├─ vision/
│  └─ <session_id>/<turn_id>/
├─ avatar/
│  └─ <session_id>/<turn_id>/
├─ tts/
│  └─ <session_id>/<turn_id>/
└─ logs/
```

## Locked Architecture Decisions

The following decisions are considered fixed for the current implementation
direction unless the project explicitly changes scope.

1. The avatar renderer is a custom parameterized 2D avatar.
2. The frontend is responsible for final avatar rendering.
3. The remote side generates structured avatar-driving outputs rather than a
   fully rendered video stream.
4. The current transport remains HTTP turn-based over SSH tunnel.
5. Future WebSocket migration must be reserved in the protocol design.
6. The local side should gradually become a light edge gateway rather than a
   heavy inference host.
7. Remote inference should host speech, vision, LLM, and avatar generation.
8. All temporary artifacts should use `/data/zifeng/siyuan/A22/tmp` rather
   than `/home`.

## Current Baseline

The current system already supports:

- local frontend text input
- local frontend audio input
- local frontend camera preview and per-turn key-frame capture scaffold
- local edge-backend forwarding for audio and video turns
- `turn_time_window` contract
- `avatar_output` placeholder contract
- local edge-backend normalization and logging
- local media packaging scaffold for `video_frames` and `video_meta`
- SSH tunnel forwarding to remote orchestrator
- remote `speech-service` scaffold with BELLE ASR runtime
- remote `vision-service` scaffold with video feature extraction endpoint
- remote `avatar-service` scaffold with viseme / expression / motion generation
- remote orchestrator + remote qwen-server
- frontend parameterized 2D avatar now consumes `avatar_output`

This means the current system already has a stable single-turn text/audio
baseline and is ready to evolve toward the final multimodal architecture.

### Current implementation status

- Module 1 is partially implemented as a local camera preview and key-frame
  capture scaffold.
- Module 2 is partially implemented as local media packaging and request
  normalization for video-aware turns.
- Module 4 is implemented as `remote/speech-service`; local legacy ASR has been
  removed from the primary path.
- Module 5 is partially implemented as `remote/vision-service`.
- Module 6 is partially implemented through orchestrator adapters for speech,
  vision, and avatar service orchestration.
- Module 7 is partially implemented as `remote/avatar-service`.
- Module 8 is partially implemented as frontend `avatar_output` consumption for
  the custom 2D renderer.

## Target System

### Local side

```text
local/
├─ frontend
│  ├─ text input
│  ├─ audio capture
│  ├─ camera capture
│  └─ parameterized 2D avatar renderer
└─ edge-backend
   ├─ session control
   ├─ turn packaging
   ├─ key-frame extraction
   ├─ media proxy
   ├─ SSH forwarding
   └─ observability
```

### Remote side

```text
remote/
├─ qwen-server
├─ speech-service
├─ vision-service
├─ avatar-service
└─ orchestrator
```

### Responsibility split

- `local/frontend`
  - capture text, audio, and camera input
  - render the 2D avatar
  - play remote-generated TTS audio
- `local/edge-backend`
  - manage sessions and turn boundaries
  - package audio/video into compact uploads
  - proxy media and orchestrator requests to remote
  - provide local logs, health, and degraded fallback behavior
- `remote/speech-service`
  - remote ASR
  - speech-side feature extraction
  - transcript and speech feature outputs
- `remote/vision-service`
  - video frame ingestion
  - face/expression/posture/attention feature extraction
- `remote/orchestrator`
  - multimodal alignment
  - context management
  - policy and psychological guidance logic
  - LLM orchestration
- `remote/avatar-service`
  - TTS generation
  - viseme generation
  - expression sequence generation
  - motion sequence generation
- `remote/qwen-server`
  - OpenAI-compatible LLM serving

## Transport and Realtime Strategy

### Current stage

- turn-based HTTP requests
- SSH tunnel as the remote transport layer
- compact audio upload
- compact video upload as key frames or short clips

This is acceptable for the current prototype and competition-stage system.

### Realtime direction

True realtime should not be implemented by sending full raw video streams over
SSH in the current stage. Instead:

1. keep models hot on the remote side
2. upload compact time-windowed media
3. process speech and vision in parallel on remote services
4. move avatar playback to incremental output later

### Future upgrade path

The protocol must reserve fields for:

- `transport_mode = websocket_stream`
- `stream_id`
- `sequence_id`
- service-side streaming audio/video/avatar events

This allows later migration from SSH + HTTP turn uploads to WebSocket-based
streaming when a new server is available.

## GPU Plan

Primary deployment assumption for the current server:

```text
GPU0: qwen-server
GPU1: speech-service + avatar-service
GPU2: vision-service
```

Practical note:

- this is the recommended deployment after `Qwen2.5-VL-7B-Instruct` and
  `CosyVoice2-0.5B` are both active in the remote stack
- if the server must temporarily keep `GPU2` unused, `vision-service` can
  share `GPU1`, but memory pressure and latency will increase

## Core Shared Contracts

### Turn Time Window

`turn_time_window` is the canonical timing envelope for a single user turn.

Fields already reserved in the shared schema:

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

Purpose:

- align audio and video within one turn
- support future stream chunk ordering
- let remote alignment know which visual frames belong to which speech window

### Avatar Output Contract

`avatar_output` is the standardized remote-to-frontend output for the
parameterized 2D avatar renderer.

Current contract fields:

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

Current renderer assumption:

```text
renderer_mode = parameterized_2d
transport_mode = http_poll
```

### Recommended viseme set for the first 2D avatar

The first renderer should use a compact viseme vocabulary:

```text
sil
a
e
i
o
u
m
f
```

This should be treated as the frontend rendering contract. Later TTS or lip-sync
models must be adapted to this vocabulary rather than forcing the renderer to
follow a model-specific phoneme system.

## The Eight Module Rollout Plan

The system should now be implemented as eight explicit modules. These modules
define both the work breakdown and the order of implementation.

### Module 1: Local Video Input Chain

Goal:

- capture camera input in the browser
- define one-turn video time windows
- sample key frames or a very short clip per turn

Frontend files to add:

```text
local/frontend/src/video/cameraTurnRecorder.js
local/frontend/src/video/frameSampler.js
local/frontend/src/video/frameEncoder.js
local/frontend/src/ui/CameraPanel.js
```

Frontend files to modify:

```text
local/frontend/src/ui/InputBar.js
local/frontend/src/main.js
local/frontend/src/styles.css
```

Acceptance:

- browser camera permission is requested and reflected in UI
- each turn can optionally carry video input
- video timing is recorded in `turn_time_window`
- video remains compact enough for SSH transport

### Module 2: Local Media Packaging and Proxy

Goal:

- make local the media gateway instead of a heavy inference host
- package audio/video with consistent turn metadata
- forward media and orchestrator requests cleanly

Local backend files to add:

```text
local/edge-backend/services/media/video_turn_service.py
local/edge-backend/services/media/frame_selector.py
local/edge-backend/services/media/media_package_builder.py
local/edge-backend/services/media/media_proxy_client.py
local/edge-backend/services/media/__init__.py
```

Local backend files to modify:

```text
local/edge-backend/config.py
local/edge-backend/models.py
local/edge-backend/routes/chat.py
local/edge-backend/services/input_preprocessor.py
```

Acceptance:

- local no longer needs to perform primary heavy ASR
- local can upload media bundles and receive media refs
- local keeps a fallback path if remote speech service is unavailable

### Module 3: Shared Protocol Upgrade

Goal:

- formalize media references
- formalize video feature inputs
- preserve future WebSocket compatibility

Shared files to modify:

```text
shared/contracts/schemas.py
shared/contracts/api_v1.md
shared/contracts/chat_request.example.json
shared/contracts/chat_response.example.json
```

New shared contract concepts:

```text
MediaIngestRequest
MediaIngestResponse
MediaRef
VideoFrameRef
VisionFeatures
SpeechFeatures
AvatarOutput
AvatarAudioCue
```

Acceptance:

- local and remote share one authoritative contract
- current HTTP mode still works
- future websocket fields remain reserved but optional

### Module 4: Remote Speech Service

Goal:

- move BELLE ASR from local to remote
- make remote ASR the primary speech pipeline
- produce transcript and speech-side features

Remote files to add:

```text
remote/speech-service/app.py
remote/speech-service/config.py
remote/speech-service/models.py
remote/speech-service/routes/transcribe.py
remote/speech-service/routes/health.py
remote/speech-service/services/asr_runtime.py
remote/speech-service/services/feature_extractor.py
remote/speech-service/services/storage.py
```

Model path:

```text
/data/zifeng/siyuan/A22/models/Belle-whisper-large-v3-turbo-zh
```

Acceptance:

- remote speech service can process uploaded audio refs
- output includes transcript, confidence, and speech features
- local BELLE becomes fallback or disabled-by-default

### Module 5: Remote Vision Service

Goal:

- process key frames or short clips
- extract structured vision features only
- avoid feeding raw video directly into the LLM

Remote files to add:

```text
remote/vision-service/app.py
remote/vision-service/config.py
remote/vision-service/models.py
remote/vision-service/routes/extract.py
remote/vision-service/routes/health.py
remote/vision-service/services/frame_feature_extractor.py
remote/vision-service/services/storage.py
```

Expected output examples:

- face presence
- expression probabilities
- head pose
- gaze / attention cues
- fatigue / agitation indicators

Acceptance:

- remote can consume uploaded video refs
- remote emits structured `vision_features`
- temporary artifacts remain under `/data/zifeng/siyuan/A22/tmp`

### Module 6: Remote Multimodal Alignment and Orchestrator Integration

Goal:

- combine speech features, vision features, and text
- produce a stable `Vision + Language` input for the LLM
- keep text-only and audio-only degradation paths

Remote orchestrator files to add or extend:

```text
remote/orchestrator/services/alignment/video_audio_alignment.py
remote/orchestrator/services/alignment/video_text_alignment.py
remote/orchestrator/services/alignment/contextual_fusion.py
remote/orchestrator/adapters/speech_client.py
remote/orchestrator/adapters/vision_client.py
remote/orchestrator/services/media_store.py
remote/orchestrator/routes/media.py
```

Remote orchestrator files to modify:

```text
remote/orchestrator/models.py
remote/orchestrator/routes/chat.py
remote/orchestrator/services/dialog_service.py
remote/orchestrator/services/policy_service.py
```

Acceptance:

- `video + audio` and `video + text` turns are both supported
- LLM receives aligned structured inputs, not raw video
- degraded operation remains available if speech or vision fails

### Module 7: Remote Avatar Service

Goal:

- convert LLM output text and style cues into avatar-driving signals
- generate TTS, visemes, expression sequence, and motion sequence

Remote files to add:

```text
remote/avatar-service/app.py
remote/avatar-service/config.py
remote/avatar-service/models.py
remote/avatar-service/routes/generate.py
remote/avatar-service/routes/health.py
remote/avatar-service/services/tts_runtime.py
remote/avatar-service/services/viseme_generator.py
remote/avatar-service/services/expression_generator.py
remote/avatar-service/services/motion_generator.py
remote/avatar-service/services/storage.py
```

Temporary output location:

```text
/data/zifeng/siyuan/A22/tmp/avatar
/data/zifeng/siyuan/A22/tmp/tts
```

Acceptance:

- remote returns a valid `avatar_output`
- frontend can play the TTS audio
- frontend can consume `viseme_seq`, `expression_seq`, and `motion_seq`

### Module 8: Frontend 2D Avatar Renderer and Degradation Strategy

Goal:

- replace the static avatar placeholder
- render a parameterized 2D avatar from `avatar_output`
- degrade cleanly when some remote modules are unavailable

Frontend files to add:

```text
local/frontend/src/avatar/renderer.js
local/frontend/src/avatar/visemeDriver.js
local/frontend/src/avatar/expressionDriver.js
local/frontend/src/avatar/motionDriver.js
local/frontend/src/avatar/audioPlayer.js
local/frontend/src/ui/AvatarPanel2D.js
```

Frontend files to modify:

```text
local/frontend/src/ui/AvatarPanel.js
local/frontend/src/main.js
local/frontend/src/styles.css
```

Degraded behavior rules:

- if avatar generation fails, still show `reply_text`
- if TTS fails, still render text and expression/motion if available
- if viseme fails, keep mouth in neutral animation
- if vision fails, fall back to audio/text alignment
- if speech fails, fall back to text-only input or browser hint when enabled

Acceptance:

- the frontend no longer shows only a static placeholder
- the avatar reacts to remote-generated cues
- user can still continue conversation under partial service failure

## Recommended Implementation Order

The recommended delivery order from the current baseline is:

1. Module 3: shared protocol upgrade
2. Module 1: local video input chain
3. Module 2: local media packaging and proxy
4. Module 4: remote speech service
5. Module 5: remote vision service
6. Module 6: remote alignment and orchestrator integration
7. Module 7: remote avatar service
8. Module 8: frontend renderer and degradation strategy

Reason:

- protocol first prevents repeated rework
- input-side capture must exist before remote services can consume media
- remote services should stabilize before avatar rendering is finalized

## Completion Definition

The architecture can be considered "system prototype complete" when all of the
following are true:

1. frontend can capture text, audio, and video
2. local can package and forward multimodal turns
3. remote speech and vision services both work
4. remote alignment produces stable LLM inputs
5. qwen-server returns text from aligned inputs
6. remote avatar service returns TTS and avatar cues
7. frontend renders a non-static 2D avatar from remote outputs
8. the system still degrades gracefully when one subservice fails

At that point, the remaining work is mainly model quality iteration, latency
optimization, UI polishing, and delivery packaging.
