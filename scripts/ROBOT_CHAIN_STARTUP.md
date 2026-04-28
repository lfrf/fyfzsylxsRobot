# RobotMatch Full Robot Chain Startup

This document starts the robot path only:

```text
Raspberry Pi raspirobot -> SSH tunnel -> remote/orchestrator -> speech-service + qwen-server
```

The robot path does not use `remote/avatar-service`.

## Remote Server

### 1. Source Environment

```bash
source /root/autodl-tmp/a22/env.sh
```

Expected model directories:

```text
/root/autodl-tmp/a22/models/Qwen2.5-7B-Instruct
/root/autodl-tmp/a22/models/Qwen3-ASR-1.7B
/root/autodl-tmp/a22/models/CosyVoice-300M-Instruct
/root/autodl-tmp/a22/models/CosyVoice
```

### 2. Start qwen-server

```bash
source "$A22_ENV_ROOT/qwen-server/bin/activate"
cd "$A22_CODE/remote/qwen-server"
export CUDA_VISIBLE_DEVICES="$QWEN_CUDA_VISIBLE_DEVICES"
python -m vllm.entrypoints.openai.api_server \
  --host 127.0.0.1 \
  --port 8000 \
  --model "$QWEN_MODEL_PATH" \
  --served-model-name "$QWEN_MODEL_NAME" \
  --dtype auto \
  --gpu-memory-utilization "$QWEN_GPU_MEMORY_UTILIZATION" \
  --max-model-len "$QWEN_MAX_MODEL_LEN" \
  --max-num-seqs "$QWEN_MAX_NUM_SEQS" \
  --trust-remote-code
```

### 3. Start speech-service ASR/TTS

```bash
source "$A22_ENV_ROOT/speech-service/bin/activate"
cd "$A22_CODE/remote/speech-service"
export ASR_PROVIDER=qwen3_asr
export ASR_MODEL=/root/autodl-tmp/a22/models/Qwen3-ASR-1.7B
export ASR_DEVICE=cuda:0
export TTS_PROVIDER=cosyvoice
export TTS_MODEL=/root/autodl-tmp/a22/models/CosyVoice-300M-Instruct
export TTS_MODE=cosyvoice_300m_instruct
export TTS_DEVICE=cuda:0
python -m uvicorn app:app --host 127.0.0.1 --port 19100
```

Health check:

```bash
curl http://127.0.0.1:19100/health
```

### 4. Start orchestrator

```bash
source "$A22_ENV_ROOT/orchestrator/bin/activate"
cd "$A22_CODE"
export SPEECH_SERVICE_BASE=http://127.0.0.1:19100
export TTS_SERVICE_BASE=http://127.0.0.1:19100
export LLM_PROVIDER=qwen
export LLM_API_BASE=http://127.0.0.1:8000/v1
export LLM_MODEL=Qwen2.5-7B-Instruct
export LLM_API_KEY=EMPTY
export ROBOT_CHAT_USE_MOCK_ASR=false
export ROBOT_CHAT_USE_MOCK_LLM=false
export ROBOT_CHAT_USE_MOCK_TTS=false
export ROBOT_LOG_LEVEL=INFO
export ROBOT_DEBUG_TRACE=true
export PYTHONPATH="$A22_CODE/shared:$A22_CODE/remote/orchestrator"
python -m uvicorn app:app --app-dir remote/orchestrator --host 127.0.0.1 --port 19000
```

Health check:

```bash
curl http://127.0.0.1:19000/health
```

## Raspberry Pi

### 1. Create local venv

```bash
cd fyfzsylxsRobot
bash scripts/setup_raspi_venv.sh
source .venv/bin/activate
bash scripts/check_raspi_env.sh
```

### 2. Establish SSH tunnel

```bash
ssh -N \
  -o ExitOnForwardFailure=yes \
  -o ServerAliveInterval=30 \
  -o ServerAliveCountMax=3 \
  -L 127.0.0.1:29000:127.0.0.1:19000 \
  -p 57547 root@connect.bjb1.seetacloud.com
```

Check from another Pi terminal:

```bash
curl http://127.0.0.1:29000/health
```

### 3. Export Pi runtime settings

```bash
export ROBOT_REMOTE_BASE_URL=http://127.0.0.1:29000
export ROBOT_AUDIO_CAPTURE_DEVICE=plughw:3,0
export ROBOT_AUDIO_PLAYBACK_DEVICE=plughw:3,0
export ROBOT_AUDIO_SAMPLE_RATE=16000
export ROBOT_AUDIO_CHANNELS=2
export ROBOT_LOG_LEVEL=INFO
export ROBOT_DEBUG_TRACE=true
```

### 4. Smoke test existing wav

```bash
python -m raspirobot.scripts.audio_tunnel_smoke --wav /tmp/robot_test.wav
```

Add `--play` after real TTS is returning a playable audio URL:

```bash
python -m raspirobot.scripts.audio_tunnel_smoke --wav /tmp/robot_test.wav --play
```

### 5. Run live loop

```bash
python -m raspirobot.scripts.live_audio_loop
```

## Current Reality

Real now:

- Raspberry Pi audio listener/VAD/wav/base64 loop;
- orchestrator ASR client;
- orchestrator Qwen OpenAI-compatible LLM client;
- orchestrator TTS client;
- speech-service `/asr/transcribe`;
- speech-service `/tts/synthesize`;
- robot TTS media proxy through orchestrator.

Reserved or mock:

- RAG retrieval;
- OLED eyes;
- servo/head hardware;
- camera and face tracking;
- wake word engine.

## Troubleshooting

- `arecord not found`: install `alsa-utils` on Raspberry Pi.
- `aplay not found`: install `alsa-utils` on Raspberry Pi.
- `pydantic missing`: activate `.venv` and run `pip install -r raspirobot/requirements.raspi.txt`.
- `qwen-server unreachable`: check `curl http://127.0.0.1:8000/v1/models` on remote.
- `speech-service unreachable`: check `curl http://127.0.0.1:19100/health` on remote.
- `TTS service unreachable`: verify `TTS_SERVICE_BASE=http://127.0.0.1:19100`.
- `audio_url download fails`: ensure Pi is using orchestrator tunnel and response URL starts with `/v1/robot/media/tts/`.
- Real ASR/LLM/TTS not being used: inspect `RobotChatResponse.debug.sources` and `RobotChatResponse.debug.fallback`.

## Validation

```bash
python -m compileall raspirobot remote/orchestrator remote/speech-service tests
git diff --check
python -m pytest tests
```
