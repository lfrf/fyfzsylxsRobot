# RobotMatch Orchestrator

Remote brain service for the Raspberry Pi robot runtime.

Active V1 endpoint:

```text
POST /v1/robot/chat_turn
Content-Type: application/json
```

The old digital-human `/chat`, `/ws/chat`, and avatar media proxy routes are not registered in the active app.

## Runtime

This service uses Python 3.11 syntax.

```bash
cd remote/orchestrator
source .venv/bin/activate
uv run uvicorn app:app --host 127.0.0.1 --port 19000
```

For SSH tunnel demos, bind to `127.0.0.1` on the remote server and forward the port from Raspberry Pi.

## Health Check

```bash
curl http://127.0.0.1:19000/health
```

## Robot Chat Smoke Request

```bash
curl -X POST http://127.0.0.1:19000/v1/robot/chat_turn \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "demo-session-001",
    "turn_id": "turn-0001",
    "mode": "elderly",
    "input": {
      "type": "audio_base64",
      "audio_base64": "UklGRiQAAABXQVZFZm10IBAAAAABAAEA",
      "audio_format": "wav",
      "sample_rate": 16000,
      "channels": 1,
      "text_hint": "切换为儿童模式"
    }
  }'
```

## Kept Remote Model Services

The robot project may reuse:

- `remote/qwen-server` for LLM;
- `remote/speech-service` for ASR and speech emotion;
- `remote/vision-service` for visual preprocessing.

`remote/avatar-service` is not part of the active robot runtime. It is retained temporarily only because it contains CosyVoice/TTS runtime code that may need extraction into a de-avatarized robot TTS service.
