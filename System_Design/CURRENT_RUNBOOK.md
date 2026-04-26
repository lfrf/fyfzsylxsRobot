# Current Runbook

## Scope

This document describes how to run the current A22 stack end to end:

- local frontend
- local edge-backend
- remote `speech-service`
- remote `vision-service`
- remote `avatar-service`
- remote `qwen-server` via vLLM
- remote `orchestrator`
- SSH tunnel from local to remote

## Remote filesystem layout

The current recommended layout separates code, uv cache, and virtual
environments:

```text
/data/zifeng/
├── .cache/uv/
└── .uv_envs/
    ├── orchestrator/
    ├── qwen-server/
    ├── speech-service/
    ├── vision-service/
    └── avatar-service/

/home/zifeng/siyuan/A22/A22_wmzjbyGroup/remote/
├── orchestrator/
├── qwen-server/
├── speech-service/
├── vision-service/
└── avatar-service/
```

Use this layout consistently so package caches do not fill `/home` and each
service has a stable dedicated environment path.

## Shared uv environment variables

Before creating or syncing any remote service environment, export:

```bash
export UV_CACHE_DIR=/data/zifeng/.cache/uv
export UV_LINK_MODE=copy
```

When working on a specific service, also export:

```bash
export UV_PROJECT_ENVIRONMENT=/data/zifeng/.uv_envs/<service-name>
```

This is important because `uv sync` otherwise defaults to a project-local
`.venv`, which is not the layout used in this deployment.

## Current architecture

The current runtime chain is:

1. browser frontend records text or audio
2. browser frontend can optionally capture camera key frames for the same turn
3. local `edge-backend` normalizes the turn and forwards audio/video payloads
4. remote `speech-service` handles ASR
5. remote `vision-service` extracts structured visual features
6. remote `orchestrator` aligns multimodal inputs and calls the remote LLM
7. remote `avatar-service` generates TTS / viseme / expression / motion outputs
8. remote response returns to local backend and then to the frontend renderer

## Recommended GPU placement

With the current real model choices, the recommended remote GPU mapping is:

1. `GPU0` -> `qwen-server`
2. `GPU1` -> `speech-service` and `avatar-service`
3. `GPU2` -> `vision-service`

This is the recommended layout for stable demo latency. If `vision-service`
must share `GPU1`, the chain can still run, but latency and memory pressure
will increase significantly.

## Start order

Use this order:

1. Start remote `qwen-server`
2. Start remote `speech-service`
3. Start remote `vision-service`
4. Start remote `avatar-service`
5. Start remote `orchestrator`
6. Create the SSH tunnel
7. Start local Docker services
8. Verify local runtime status
9. Run end-to-end tests

## Copy-Paste Command Blocks

The blocks below are designed to be copied and executed as complete chunks.
They assume:

- code lives under `/home/zifeng/siyuan/A22/A22_wmzjbyGroup/remote`
- uv cache lives under `/data/zifeng/.cache/uv`
- virtual environments live under `/data/zifeng/.uv_envs`

Python interpreter note:

- use `uv venv --python /home/zifeng/.local/bin/python3.11 ...`
- the current remote host should use the exact interpreter path above
- after activation, `which python3.11` should point into the target service
  environment, for example:

```bash
which python3.11
# /data/zifeng/.uv_envs/speech-service/bin/python3.11
```

### qwen-server: create environment and start

```bash
export UV_CACHE_DIR=/data/zifeng/.cache/uv
export UV_LINK_MODE=copy
export UV_PROJECT_ENVIRONMENT=/data/zifeng/.uv_envs/qwen-server

cd /home/zifeng/siyuan/A22/A22_wmzjbyGroup/remote/qwen-server
rm -rf .venv
uv venv --python /home/zifeng/.local/bin/python3.11 "$UV_PROJECT_ENVIRONMENT"
source /data/zifeng/.uv_envs/qwen-server/bin/activate
uv sync

export CUDA_VISIBLE_DEVICES=0
which python3.11
python -c "import sys, vllm; print(sys.executable); print(vllm.__version__)"
python -m vllm.entrypoints.openai.api_server \
  --host 127.0.0.1 \
  --port 8000 \
  --model /data/zifeng/siyuan/A22/models/Qwen2.5-7B-Instruct \
  --served-model-name Qwen2.5-7B-Instruct \
  --dtype auto \
  --gpu-memory-utilization 0.90 \
  --trust-remote-code
```

### qwen-server: start only

```bash
export UV_CACHE_DIR=/data/zifeng/.cache/uv
export UV_LINK_MODE=copy
export UV_PROJECT_ENVIRONMENT=/data/zifeng/.uv_envs/qwen-server

cd /home/zifeng/siyuan/A22/A22_wmzjbyGroup/remote/qwen-server
source /data/zifeng/.uv_envs/qwen-server/bin/activate

export CUDA_VISIBLE_DEVICES=0
python -m vllm.entrypoints.openai.api_server \
  --host 127.0.0.1 \
  --port 8000 \
  --model /data/zifeng/siyuan/A22/models/Qwen2.5-7B-Instruct \
  --served-model-name Qwen2.5-7B-Instruct \
  --dtype auto \
  --gpu-memory-utilization 0.90 \
  --trust-remote-code
```

### speech-service: create environment and start

```bash
export UV_CACHE_DIR=/data/zifeng/.cache/uv
export UV_LINK_MODE=copy
export UV_PROJECT_ENVIRONMENT=/data/zifeng/.uv_envs/speech-service

cd /home/zifeng/siyuan/A22/A22_wmzjbyGroup/remote/speech-service
rm -rf /data/zifeng/.uv_envs/speech-service
rm -rf .venv
uv venv --python /home/zifeng/.local/bin/python3.11 "$UV_PROJECT_ENVIRONMENT"
source /data/zifeng/.uv_envs/speech-service/bin/activate
uv sync

export CUDA_VISIBLE_DEVICES=1
export ASR_MODEL=/data/zifeng/siyuan/A22/models/Belle-whisper-large-v3-turbo-zh
export ASR_DEVICE=cuda:0
which python3.11
uv pip list | grep -E 'torch|torchaudio|nvidia|triton'
python -c "import torch; print(torch.__version__); print(torch.version.cuda); print(torch.cuda.is_available())"
uvicorn app:app --host 127.0.0.1 --port 19100
```

### speech-service: start only

```bash
export UV_CACHE_DIR=/data/zifeng/.cache/uv
export UV_LINK_MODE=copy
export UV_PROJECT_ENVIRONMENT=/data/zifeng/.uv_envs/speech-service

cd /home/zifeng/siyuan/A22/A22_wmzjbyGroup/remote/speech-service
source /data/zifeng/.uv_envs/speech-service/bin/activate

export CUDA_VISIBLE_DEVICES=1
export ASR_MODEL=/data/zifeng/siyuan/A22/models/Belle-whisper-large-v3-turbo-zh
export ASR_DEVICE=cuda:0
which python3.11
uv pip list | grep -E 'torch|torchaudio|nvidia|triton'
python -c "import torch; print(torch.__version__); print(torch.version.cuda); print(torch.cuda.is_available())"
uvicorn app:app --host 127.0.0.1 --port 19100
```

### vision-service: create environment and start

```bash
export UV_CACHE_DIR=/data/zifeng/.cache/uv
export UV_LINK_MODE=copy
export UV_PROJECT_ENVIRONMENT=/data/zifeng/.uv_envs/vision-service

cd /home/zifeng/siyuan/A22/A22_wmzjbyGroup/remote/vision-service
rm -rf .venv
uv venv --python /home/zifeng/.local/bin/python3.11 "$UV_PROJECT_ENVIRONMENT"
source /data/zifeng/.uv_envs/vision-service/bin/activate
uv sync

export VISION_EXTRACTOR_MODE=qwen2_5_vl
export VISION_MODEL=/data/zifeng/siyuan/A22/models/Qwen2.5-VL-7B-Instruct
export CUDA_VISIBLE_DEVICES=2
export VISION_DEVICE=cuda:0
which python3.11
uv pip list | grep -E 'torch|nvidia|triton'
python -c "import torch; print(torch.__version__); print(torch.version.cuda); print(torch.cuda.is_available())"
uvicorn app:app --host 127.0.0.1 --port 19200
```

### vision-service: start only

```bash
export UV_CACHE_DIR=/data/zifeng/.cache/uv
export UV_LINK_MODE=copy
export UV_PROJECT_ENVIRONMENT=/data/zifeng/.uv_envs/vision-service

cd /home/zifeng/siyuan/A22/A22_wmzjbyGroup/remote/vision-service
source /data/zifeng/.uv_envs/vision-service/bin/activate

export VISION_EXTRACTOR_MODE=qwen2_5_vl
export VISION_MODEL=/data/zifeng/siyuan/A22/models/Qwen2.5-VL-7B-Instruct
export CUDA_VISIBLE_DEVICES=2
export VISION_DEVICE=cuda:0
which python3.11
uv pip list | grep -E 'torch|nvidia|triton'
python -c "import torch; print(torch.__version__); print(torch.version.cuda); print(torch.cuda.is_available())"
uvicorn app:app --host 127.0.0.1 --port 19200
```

### avatar-service: create environment and start

```bash
export UV_CACHE_DIR=/data/zifeng/.cache/uv
export UV_LINK_MODE=copy
export UV_PROJECT_ENVIRONMENT=/data/zifeng/.uv_envs/avatar-service

cd /home/zifeng/siyuan/A22/A22_wmzjbyGroup/remote/avatar-service
rm -rf .venv
uv venv --python /home/zifeng/.local/bin/python3.11 "$UV_PROJECT_ENVIRONMENT"
source /data/zifeng/.uv_envs/avatar-service/bin/activate
uv sync

if [ ! -d /data/zifeng/siyuan/A22/models/CosyVoice ]; then
  git clone --recursive https://github.com/FunAudioLLM/CosyVoice.git /data/zifeng/siyuan/A22/models/CosyVoice
fi
cd /data/zifeng/siyuan/A22/models/CosyVoice
git submodule update --init --recursive

cd /home/zifeng/siyuan/A22/A22_wmzjbyGroup/remote/avatar-service
export TTS_MODE=cosyvoice2_sft
export TTS_MODEL=/data/zifeng/siyuan/A22/models/CosyVoice2-0.5B
export CUDA_VISIBLE_DEVICES=1
export TTS_DEVICE=cuda:0
export TTS_REPO_PATH=/data/zifeng/siyuan/A22/models/CosyVoice
which python3.11
uv pip list | grep -E 'torch|torchaudio|nvidia|triton|onnxruntime'
python -c "import torch, torchaudio; print(torch.__version__); print(torch.version.cuda); print(torch.cuda.is_available()); print(torchaudio.__version__)"
uvicorn app:app --host 127.0.0.1 --port 19300
```

### avatar-service: start only

```bash
export UV_CACHE_DIR=/data/zifeng/.cache/uv
export UV_LINK_MODE=copy
export UV_PROJECT_ENVIRONMENT=/data/zifeng/.uv_envs/avatar-service

cd /home/zifeng/siyuan/A22/A22_wmzjbyGroup/remote/avatar-service
source /data/zifeng/.uv_envs/avatar-service/bin/activate

export TTS_MODE=cosyvoice2_sft
export TTS_MODEL=/data/zifeng/siyuan/A22/models/CosyVoice2-0.5B
export CUDA_VISIBLE_DEVICES=1
export TTS_DEVICE=cuda:0
export TTS_REPO_PATH=/data/zifeng/siyuan/A22/models/CosyVoice
which python3.11
uv pip list | grep -E 'torch|torchaudio|nvidia|triton|onnxruntime'
python -c "import torch, torchaudio; print(torch.__version__); print(torch.version.cuda); print(torch.cuda.is_available()); print(torchaudio.__version__)"
uvicorn app:app --host 127.0.0.1 --port 19300
```

### orchestrator: create environment and start

```bash
export UV_CACHE_DIR=/data/zifeng/.cache/uv
export UV_LINK_MODE=copy
export UV_PROJECT_ENVIRONMENT=/data/zifeng/.uv_envs/orchestrator

cd /home/zifeng/siyuan/A22/A22_wmzjbyGroup/remote/orchestrator
rm -rf .venv
uv venv --python /home/zifeng/.local/bin/python3.11 "$UV_PROJECT_ENVIRONMENT"
source /data/zifeng/.uv_envs/orchestrator/bin/activate
uv sync

export LLM_PROVIDER=qwen
export LLM_MODEL=Qwen2.5-7B-Instruct
export LLM_API_BASE=http://127.0.0.1:8000/v1
export LLM_API_KEY=EMPTY
export LLM_REQUEST_TIMEOUT_SECONDS=60
which python3.11
python -c "import sys, fastapi, httpx; print(sys.executable); print(fastapi.__version__); print(httpx.__version__)"
uv run uvicorn app:app --host 127.0.0.1 --port 19000
```

### orchestrator: start only

```bash
export UV_CACHE_DIR=/data/zifeng/.cache/uv
export UV_LINK_MODE=copy
export UV_PROJECT_ENVIRONMENT=/data/zifeng/.uv_envs/orchestrator

cd /home/zifeng/siyuan/A22/A22_wmzjbyGroup/remote/orchestrator
source /data/zifeng/.uv_envs/orchestrator/bin/activate

export LLM_PROVIDER=qwen
export LLM_MODEL=Qwen2.5-7B-Instruct
export LLM_API_BASE=http://127.0.0.1:8000/v1
export LLM_API_KEY=EMPTY
export LLM_REQUEST_TIMEOUT_SECONDS=60
uv run uvicorn app:app --host 127.0.0.1 --port 19000
```

## Remote server: qwen-server

Recommended server path:

```bash
/home/zifeng/siyuan/A22/A22_wmzjbyGroup/remote/qwen-server
```

Recommended model path:

```bash
/data/zifeng/siyuan/A22/models/Qwen2.5-7B-Instruct
```

Create and prepare the environment:

```bash
cd /home/zifeng/siyuan/A22/A22_wmzjbyGroup/remote
mkdir -p qwen-server
cd qwen-server
export UV_CACHE_DIR=/data/zifeng/.cache/uv
export UV_LINK_MODE=copy
export UV_PROJECT_ENVIRONMENT=/data/zifeng/.uv_envs/qwen-server
uv venv --python /home/zifeng/.local/bin/python3.11 "$UV_PROJECT_ENVIRONMENT"
uv sync
source /data/zifeng/.uv_envs/qwen-server/bin/activate
python -c "import sys, vllm; print(sys.executable); print(vllm.__version__)"
```

Start vLLM on a selected GPU:

```bash
cd /home/zifeng/siyuan/A22/A22_wmzjbyGroup/remote/qwen-server
export UV_CACHE_DIR=/data/zifeng/.cache/uv
export UV_LINK_MODE=copy
export UV_PROJECT_ENVIRONMENT=/data/zifeng/.uv_envs/qwen-server
source /data/zifeng/.uv_envs/qwen-server/bin/activate
export CUDA_VISIBLE_DEVICES=<cuda_id>
python -m vllm.entrypoints.openai.api_server \
  --host 127.0.0.1 \
  --port 8000 \
  --model /data/zifeng/siyuan/A22/models/Qwen2.5-7B-Instruct \
  --served-model-name Qwen2.5-7B-Instruct \
  --dtype auto \
  --gpu-memory-utilization 0.90 \
  --trust-remote-code
```

Notes:

- `<cuda_id>` can be `0`, `1`, or `2`
- this selects a single physical GPU for the vLLM process
- the current 7B model can run as a single-GPU deployment
- recommended value here is `0`
- if `uv sync` was already run without `UV_PROJECT_ENVIRONMENT`, remove the
  accidentally created project-local `.venv` before retrying

Verify on the server:

```bash
curl http://127.0.0.1:8000/v1/models
```

## Remote server: orchestrator

Prepare the environment:

```bash
cd /home/zifeng/siyuan/A22/A22_wmzjbyGroup/remote/orchestrator
export UV_CACHE_DIR=/data/zifeng/.cache/uv
export UV_LINK_MODE=copy
export UV_PROJECT_ENVIRONMENT=/data/zifeng/.uv_envs/orchestrator
uv venv --python /home/zifeng/.local/bin/python3.11 "$UV_PROJECT_ENVIRONMENT"
source /data/zifeng/.uv_envs/orchestrator/bin/activate
uv sync
```

If the environment already exists:

```bash
cd /home/zifeng/siyuan/A22/A22_wmzjbyGroup/remote/orchestrator
export UV_CACHE_DIR=/data/zifeng/.cache/uv
export UV_LINK_MODE=copy
export UV_PROJECT_ENVIRONMENT=/data/zifeng/.uv_envs/orchestrator
source /data/zifeng/.uv_envs/orchestrator/bin/activate
uv sync
```

Start orchestrator:

```bash
cd /home/zifeng/siyuan/A22/A22_wmzjbyGroup/remote/orchestrator
export UV_CACHE_DIR=/data/zifeng/.cache/uv
export UV_LINK_MODE=copy
export UV_PROJECT_ENVIRONMENT=/data/zifeng/.uv_envs/orchestrator
source /data/zifeng/.uv_envs/orchestrator/bin/activate
export LLM_PROVIDER=qwen
export LLM_MODEL=Qwen2.5-7B-Instruct
export LLM_API_BASE=http://127.0.0.1:8000/v1
export LLM_API_KEY=EMPTY
export LLM_REQUEST_TIMEOUT_SECONDS=60
uv run uvicorn app:app --host 127.0.0.1 --port 19000
```

Verify on the server:

```bash
curl http://127.0.0.1:19000/health
```

## Remote server: speech-service

Prepare the environment:

```bash
cd /home/zifeng/siyuan/A22/A22_wmzjbyGroup/remote/speech-service
export UV_CACHE_DIR=/data/zifeng/.cache/uv
export UV_LINK_MODE=copy
export UV_PROJECT_ENVIRONMENT=/data/zifeng/.uv_envs/speech-service
uv venv --python /home/zifeng/.local/bin/python3.11 "$UV_PROJECT_ENVIRONMENT"
source /data/zifeng/.uv_envs/speech-service/bin/activate
uv sync
```

Start speech-service on the GPU chosen for BELLE ASR:

```bash
cd /home/zifeng/siyuan/A22/A22_wmzjbyGroup/remote/speech-service
export UV_CACHE_DIR=/data/zifeng/.cache/uv
export UV_LINK_MODE=copy
export UV_PROJECT_ENVIRONMENT=/data/zifeng/.uv_envs/speech-service
source /data/zifeng/.uv_envs/speech-service/bin/activate
export CUDA_VISIBLE_DEVICES=1
export ASR_MODEL=/data/zifeng/siyuan/A22/models/Belle-whisper-large-v3-turbo-zh
export ASR_DEVICE=cuda:0
uvicorn app:app --host 127.0.0.1 --port 19100
```

Verify:

```bash
curl http://127.0.0.1:19100/health
```

## Remote server: vision-service

Prepare and start:

```bash
cd /home/zifeng/siyuan/A22/A22_wmzjbyGroup/remote/vision-service
export UV_CACHE_DIR=/data/zifeng/.cache/uv
export UV_LINK_MODE=copy
export UV_PROJECT_ENVIRONMENT=/data/zifeng/.uv_envs/vision-service
uv venv --python /home/zifeng/.local/bin/python3.11 "$UV_PROJECT_ENVIRONMENT"
source /data/zifeng/.uv_envs/vision-service/bin/activate
uv sync
export VISION_EXTRACTOR_MODE=qwen2_5_vl
export VISION_MODEL=/data/zifeng/siyuan/A22/models/Qwen2.5-VL-7B-Instruct
export CUDA_VISIBLE_DEVICES=2
export VISION_DEVICE=cuda:0
uvicorn app:app --host 127.0.0.1 --port 19200
```

Verify:

```bash
curl http://127.0.0.1:19200/health
```

## Remote server: avatar-service

Prepare and start:

```bash
cd /home/zifeng/siyuan/A22/A22_wmzjbyGroup/remote/avatar-service
export UV_CACHE_DIR=/data/zifeng/.cache/uv
export UV_LINK_MODE=copy
export UV_PROJECT_ENVIRONMENT=/data/zifeng/.uv_envs/avatar-service
uv venv --python /home/zifeng/.local/bin/python3.11 "$UV_PROJECT_ENVIRONMENT"
source /data/zifeng/.uv_envs/avatar-service/bin/activate
uv sync
git clone --recursive https://github.com/FunAudioLLM/CosyVoice.git /data/zifeng/siyuan/A22/models/CosyVoice
export TTS_MODE=cosyvoice2_sft
export TTS_MODEL=/data/zifeng/siyuan/A22/models/CosyVoice2-0.5B
export CUDA_VISIBLE_DEVICES=1
export TTS_DEVICE=cuda:0
export TTS_REPO_PATH=/data/zifeng/siyuan/A22/models/CosyVoice
uvicorn app:app --host 127.0.0.1 --port 19300
```

Notes:

- `CosyVoice2-0.5B` weights alone are not sufficient; `avatar-service` also
  needs the CosyVoice runtime codebase available under `TTS_REPO_PATH`
- after cloning CosyVoice, ensure submodules are initialized:

```bash
cd /data/zifeng/siyuan/A22/models/CosyVoice
git submodule update --init --recursive
```

Compatibility note:

- `pyproject.toml` is now the authoritative uv environment file for
  `speech-service`, `vision-service`, and `avatar-service`
- `requirements.txt` is retained as a compatibility fallback for non-uv flows

Verify:

```bash
curl http://127.0.0.1:19300/health
```

## Local machine: SSH tunnel

Create the tunnel from local to remote:

```bash
ssh -N -L 19000:127.0.0.1:19000 <server_user>@<server_host>
```

Verify locally:

```bash
curl http://127.0.0.1:19000/health
curl -X POST http://127.0.0.1:19000/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id":"demo-001","turn_id":1,"user_text":"hello","input_type":"text"}'
```

## Local machine: frontend and edge-backend

Start local services:

```bash
cd /home/siyuen/docker_ws/A22
docker compose -f compose.yaml -f compose.local.yaml up -d --force-recreate
```

Check service status:

```bash
docker compose -f compose.yaml -f compose.local.yaml ps
docker compose -f compose.yaml -f compose.local.yaml logs -f edge-backend
```

## Local runtime notes

The local `edge-backend` is now a forwarding layer only. Audio turns should be
observed on:

- `speech-service /transcribe`
- `vision-service /extract` when camera frames are attached
- `avatar-service /generate` after the LLM reply is produced

The port chain is:

- browser -> `nginx:80`
- `nginx` -> `edge-backend:8000`
- local `edge-backend` -> `http://host.docker.internal:19000/chat`
- SSH tunnel local `19000` -> remote `127.0.0.1:19000`
- remote `orchestrator:19000` -> `speech-service:19100`
- remote `orchestrator:19000` -> `vision-service:19200`
- remote `orchestrator:19000` -> `avatar-service:19300`
- remote `orchestrator:19000` -> `qwen-server:8000/v1`

Watch the local logs:

```bash
tail -f /home/siyuen/docker_ws/A22/logs/edge-backend/edge-backend-events-*.log
```

Or use the compact listener:

```bash
python3 /home/siyuen/docker_ws/A22/a22_demo/listen_bridge.py
```

## End-to-end test

Test remote orchestrator from local:

```bash
curl http://127.0.0.1:19000/health
```

Test the local edge-backend directly:

```bash
curl http://localhost:8000/health
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id":"demo-001","turn_id":1,"user_text":"测试文本链路","input_type":"text"}'
```

Test the browser UI:

```text
http://localhost
```

Recommended test order:

1. send one text turn
2. verify remote response is returned
3. send one audio turn
4. check `asr_transcription` in local logs
5. check `bridge_outbound` and `bridge_inbound`

## Shutdown

Stop local containers:

```bash
cd /home/siyuen/docker_ws/A22
docker compose -f compose.yaml -f compose.local.yaml down
```

Stop the SSH tunnel:

```bash
pkill -f "ssh -N -L 19000:127.0.0.1:19000"
```

Stop remote services by interrupting their running terminals.

## AutoDL custom service single-port proxy

When the remote host runs on AutoDL and only one external custom-service
entrypoint is available, the working setup is:

- `orchestrator` on `127.0.0.1:19000`
- `proxy_in_instance` on `127.0.0.1:6006`
- `nginx` on `0.0.0.0:6008`
- AutoDL custom-service URL `8443 -> 6008`

Reference configs:

- [proxy-config.yaml](D:\a22\FuChuangSai_A22\infra\autodl\proxy-config.yaml)
- [autodl-6008-proxy.conf](D:\a22\FuChuangSai_A22\infra\nginx\autodl-6008-proxy.conf)

Recommended remote layout:

```text
/root/autodl-tmp/a22/config.yaml
/root/autodl-tmp/a22/proxy_in_instance
/root/autodl-tmp/a22/code/FuChuangSai_A22/infra/autodl/proxy-config.yaml
/root/autodl-tmp/a22/code/FuChuangSai_A22/infra/nginx/autodl-6008-proxy.conf
```

Install nginx if needed:

```bash
apt-get update
apt-get install -y nginx
```

Start the core backend services first:

```bash
curl http://127.0.0.1:8000/v1/models
curl http://127.0.0.1:19300/health
curl http://127.0.0.1:19000/health
```

Prepare and start `proxy_in_instance` on `6006`:

```bash
cd /root/autodl-tmp/a22
wget https://autodl-public.ks3-cn-beijing.ksyuncs.com/tool/api-proxy/proxy_in_instance
chmod +x proxy_in_instance
cp /root/autodl-tmp/a22/code/FuChuangSai_A22/infra/autodl/proxy-config.yaml /root/autodl-tmp/a22/config.yaml
tmux kill-session -t autodl-proxy 2>/dev/null || true
tmux new-session -d -s autodl-proxy "cd /root/autodl-tmp/a22 && ./proxy_in_instance"
```

Verify the internal AutoDL proxy:

```bash
tmux capture-pane -pt autodl-proxy -S -50
curl http://127.0.0.1:6006/health
curl -X POST http://127.0.0.1:6006/chat \
  -H 'Content-Type: application/json' \
  -d '{"session_id":"debug-chat","turn_id":1,"user_text":"你好","input_type":"text","client_ts":1234567890,"turn_time_window":{"window_id":"debug-chat-turn-1","source_clock":"browser_epoch_ms","transport_mode":"http_turn","sequence_id":1,"capture_started_at_ms":1234567890,"capture_ended_at_ms":1234567890,"window_duration_ms":0}}'
```

Then start the AutoDL-facing nginx proxy on `6008`. This nginx should proxy all
paths to `127.0.0.1:6006`, not directly to `19000`.

```bash
nginx -s stop 2>/dev/null || true
tmux kill-session -t autodl-nginx 2>/dev/null || true
tmux new-session -d -s autodl-nginx \
  "nginx -c /root/autodl-tmp/a22/code/FuChuangSai_A22/infra/nginx/autodl-6008-proxy.conf -g 'daemon off;'"
```

Verify inside the server:

```bash
curl http://127.0.0.1:6008/health
curl -X POST http://127.0.0.1:6008/chat \
  -H 'Content-Type: application/json' \
  -d '{"session_id":"debug-chat","turn_id":2,"user_text":"你好","input_type":"text","client_ts":1234567890,"turn_time_window":{"window_id":"debug-chat-turn-2","source_clock":"browser_epoch_ms","transport_mode":"http_turn","sequence_id":2,"capture_started_at_ms":1234567890,"capture_ended_at_ms":1234567890,"window_duration_ms":0}}'
```

Then use the AutoDL custom-service URL that maps to `6008` and access:

```text
https://<autodl-custom-service-host>:8443/health
https://<autodl-custom-service-host>:8443/chat
https://<autodl-custom-service-host>:8443/media/video/<session_id>/<turn_id>
```

Verify from the local machine:

```powershell
curl.exe -k https://<autodl-custom-service-host>:8443/health
```

```powershell
Invoke-RestMethod `
  -Uri "https://<autodl-custom-service-host>:8443/chat" `
  -Method Post `
  -ContentType "application/json" `
  -Body (@{
    session_id = "debug-chat"
    turn_id = 3
    user_text = "你好"
    input_type = "text"
    client_ts = 1234567890
    turn_time_window = @{
      window_id = "debug-chat-turn-3"
      source_clock = "browser_epoch_ms"
      transport_mode = "http_turn"
      sequence_id = 3
      capture_started_at_ms = 1234567890
      capture_ended_at_ms = 1234567890
      window_duration_ms = 0
    }
  } | ConvertTo-Json -Depth 5)
```

Important constraints:

1. Keep `orchestrator` on `127.0.0.1:19000`.
2. Let `proxy_in_instance` own `127.0.0.1:6006`.
3. Let `nginx` own `0.0.0.0:6008`.
4. Do not let both `nginx` and another process bind the same `6008`.
5. Keep the frontend target on the AutoDL public URL. Do not point the browser
   directly at internal `127.0.0.1:6006`.
