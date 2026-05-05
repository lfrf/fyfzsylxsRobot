# User Profile and Face Identity

## 1. Architecture

RobotMatch keeps user profile data on the remote side. Raspberry Pi can send audio text hints and, later, selected video frames. The remote services turn those signals into a stable `user_id`, compact profile context, memory events, and short LLM prompt context.

```text
Pi audio/video
  -> remote/vision-service face identity
  -> face_id
  -> remote/orchestrator identity resolution
  -> user_id/profile/memory
  -> compact profile context
  -> LLM prompt
```

The Pi does not store profile snapshots, memory files, face maps, or face embeddings.

## 2. Data Flow

1. Pi sends `text_hint` and optional vision context to `/v1/robot/chat_turn`.
2. For local testing, `request_options.mock_user_id` can directly choose the remote user.
3. For face-based identity, vision-service accepts an image or video frames at `/v1/vision/identity/extract`.
4. vision-service returns `face_identity.face_id`.
5. orchestrator maps `face_id` to a `user_id`, creates or loads the profile, and builds compact profile context.
6. LLMClient receives `user_profile_context` for all modes.
7. RobotChatService writes a memory event after a reply and updates profile summary only when trigger rules request it.

## 3. Storage Paths

Profile data:

```text
remote/orchestrator/data/profiles/
  users.json
  face_user_map.json
  memories/{user_id}.jsonl
  snapshots/{user_id}.json
  snapshots/{user_id}.md
```

Face identity database:

```text
remote/vision-service/data/faces/faces.json
```

The face db stores `face_id`, normalized embedding, optional `user_id`, `seen_count`, timestamps, source, and embedding model. It does not store raw face images by default.

## 4. Environment Variables

orchestrator:

```text
PROFILE_DATA_DIR=remote/orchestrator/data/profiles
PROFILE_CONTEXT_MAX_CHARS=800
PROFILE_SUMMARIZE_EVERY_TURNS=6
PROFILE_SUMMARY_PROVIDER=rule
PROFILE_MEMORY_ENABLED=true
```

vision-service:

```text
FACE_RECOGNITION_PROVIDER=mock
FACE_DB_DIR=remote/vision-service/data/faces
FACE_MATCH_THRESHOLD=0.6
FACE_CREATE_UNKNOWN=true
FACE_STORE_RAW_IMAGES=false
INSIGHTFACE_MODEL_NAME=buffalo_l
INSIGHTFACE_DET_SIZE=640,640
INSIGHTFACE_CTX_ID=-1
```

`FACE_DB_PATH`, `FACE_INSIGHTFACE_MODEL`, `FACE_INSIGHTFACE_DET_SIZE`, and `FACE_INSIGHTFACE_CTX_ID` are also accepted as compatibility aliases.

## 5. mock_user_id Test Request

```json
{
  "session_id": "demo-session-001",
  "turn_id": "turn-profile-001",
  "mode": "care",
  "input": {
    "type": "audio_base64",
    "audio_base64": "UklGRiQAAABXQVZFZm10IBAAAAABAAEA",
    "audio_format": "wav",
    "sample_rate": 16000,
    "channels": 1,
    "text_hint": "我今天有点累"
  },
  "request_options": {
    "mock_user_id": "user_test_001",
    "mock_display_name": "小明",
    "force_profile_summarize": true
  }
}
```

Expected debug shape:

```json
{
  "profile": {
    "used": true,
    "user_id": "user_test_001",
    "identity_source": "mock_user_id",
    "profile_context_chars": 1,
    "memory_written": true,
    "summary_updated": true
  }
}
```

## 6. face_id Flow

Call vision-service first:

```bash
curl -X POST http://127.0.0.1:8001/v1/vision/identity/extract \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "demo-session-001",
    "turn_id": "vision-turn-001",
    "image_base64": "BASE64_JPEG_OR_PNG"
  }'
```

Then pass the returned `face_identity.face_id` into `/v1/robot/chat_turn` through `request_options.face_id` or `vision_context.face_identity.face_id`.

## 7. InsightFace

Mock is the default and is suitable for tests:

```text
FACE_RECOGNITION_PROVIDER=mock
```

To enable InsightFace:

```bash
pip install insightface onnxruntime opencv-python numpy
export FACE_RECOGNITION_PROVIDER=insightface
export INSIGHTFACE_MODEL_NAME=buffalo_l
export INSIGHTFACE_DET_SIZE=640,640
export INSIGHTFACE_CTX_ID=-1
```

InsightFace is imported lazily only when the provider is `insightface`. Missing InsightFace or ONNXRuntime does not affect mock-provider tests.

## 8. Profile API

```bash
curl http://127.0.0.1:8000/v1/profiles/user_test_001
curl http://127.0.0.1:8000/v1/profiles/by-face/face_abc123
curl -X POST http://127.0.0.1:8000/v1/profiles/user_test_001/summarize
```

## 9. Vision Identity API

Endpoint:

```text
POST /v1/vision/identity/extract
```

Minimal response fields:

```json
{
  "face_identity": {
    "face_detected": true,
    "face_id": "face_abc123",
    "user_id": null,
    "is_known": false,
    "match_confidence": null,
    "source": "mock",
    "seen_count": 1,
    "last_seen_at": "2026-05-05T00:00:00+00:00"
  },
  "face_observations": [],
  "processed_frame_count": 1,
  "provider": "mock"
}
```

## 10. Privacy Notes

- Raw face images are not saved by default.
- Default storage keeps `face_id`, embedding, optional `user_id`, timestamps, and user profile data.
- Pi local runtime does not store user profiles, long-term memory, or face embeddings.
- LLM prompt injection is compact and natural; it should not expose internal database, memory, or profile-system wording to the user.
