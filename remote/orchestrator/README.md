# RobotMatch Orchestrator

Remote brain service for the Raspberry Pi robot runtime.

Active V1 endpoint:

```text
POST /v1/robot/chat_turn
Content-Type: application/json
```

The old digital-human `/chat`, `/ws/chat`, and avatar media proxy routes are not registered in the active app.

The active robot path is layered:

```text
routes/robot_chat.py
  -> services/robot_chat_service.py
  -> clients/asr_client.py      -> remote/speech-service /asr/transcribe
  -> clients/llm_client.py      -> remote/qwen-server /v1/chat/completions
  -> clients/tts_client.py      -> remote/speech-service /tts/synthesize
  -> routes/robot_media.py      -> proxies TTS wav for Raspberry Pi tunnel access
```

## Runtime

This service uses Python 3.11 syntax.

```bash
cd remote/orchestrator
source .venv/bin/activate
export SPEECH_SERVICE_BASE=http://127.0.0.1:19100
export TTS_SERVICE_BASE=http://127.0.0.1:19200
export LLM_PROVIDER=qwen
export LLM_API_BASE=http://127.0.0.1:8000/v1
export LLM_MODEL=Qwen2.5-7B-Instruct
export LLM_API_KEY=EMPTY
export ROBOT_CHAT_USE_MOCK_ASR=false
export ROBOT_CHAT_USE_MOCK_LLM=false
export ROBOT_CHAT_USE_MOCK_TTS=false
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
    "mode": "care",
    "input": {
      "type": "audio_base64",
      "audio_base64": "UklGRiQAAABXQVZFZm10IBAAAAABAAEA",
      "audio_format": "wav",
      "sample_rate": 16000,
      "channels": 1,
      "text_hint": "切换为游戏模式"
    }
  }'
```

## Kept Remote Model Services

The robot project may reuse:

- `remote/qwen-server` for LLM;
- `remote/speech-service` for ASR, robot TTS, and speech emotion;
- `remote/vision-service` for visual preprocessing.

`remote/avatar-service` is not part of the active robot runtime. Robot TTS is now represented as standalone speech synthesis under `remote/speech-service` and must not return avatar, viseme, lip-sync, or video fields.
