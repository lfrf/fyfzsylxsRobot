# Remote Docker Runbook (One Model Per Container)

This runbook deploys all remote model services in isolated Docker containers:

- `qwen-server` (vLLM LLM)
- `speech-service` (ASR)
- `vision-service` (vision extraction)
- `avatar-service` (TTS/avatar generation)
- `orchestrator` (service coordinator)

## 1. Prerequisites

1. GPU server with Docker + NVIDIA Container Toolkit.
2. Model directories prepared under a shared model root (default `/root/autodl-tmp/a22/models`).
3. Repo root is `FuChuangSai_A22`.

Required model folders (default):

- `/root/autodl-tmp/a22/models/Qwen2.5-7B-Instruct`
- `/root/autodl-tmp/a22/models/Qwen3-ASR-1.7B`
- `/root/autodl-tmp/a22/models/Qwen2.5-VL-7B-Instruct`
- `/root/autodl-tmp/a22/models/CosyVoice2-0.5B`
- `/root/autodl-tmp/a22/models/CosyVoice`

## 2. Prepare environment file

```bash
cd /path/to/FuChuangSai_A22
cp .env.remote.models.example .env.remote.models
```

Edit `.env.remote.models` based on your server paths and GPU assignment.

## 3. Start all remote containers

```bash
docker compose --env-file .env.remote.models -f compose.yaml -f compose.remote.models.yaml up -d --build
```

## 4. Verify health

```bash
curl -s http://127.0.0.1:8000/v1/models
curl -s http://127.0.0.1:19100/health
curl -s http://127.0.0.1:19200/health
curl -s http://127.0.0.1:19300/health
curl -s http://127.0.0.1:19000/health
```

Expected key points:

- speech `/health` returns `asr_provider=qwen3_asr`
- orchestrator `/health` returns `llm_provider=qwen`

## 5. Local bridge usage

Local edge-backend keeps pointing to remote orchestrator `19000`.
If using SSH tunnel on local machine:

```bash
ssh -N -L 19000:127.0.0.1:19000 -p <PORT> root@<HOST>
```

Then local stack can continue using:

- `CLOUD_API_BASE=http://host.docker.internal:19000`
- `CLOUD_WS_CHAT_ENDPOINT=ws://host.docker.internal:19000/ws/chat`

## 6. Logs and troubleshooting

```bash
docker compose --env-file .env.remote.models -f compose.yaml -f compose.remote.models.yaml ps
docker compose --env-file .env.remote.models -f compose.yaml -f compose.remote.models.yaml logs -f orchestrator
docker compose --env-file .env.remote.models -f compose.yaml -f compose.remote.models.yaml logs -f speech-service
```

If `speech-service` fails because of ASR model/config, verify:

- `ASR_PROVIDER` and `ASR_MODEL_PATH` in `.env.remote.models`
- model folder actually exists and contains full weights
- GPU memory is sufficient

## 7. Stop and save cost

```bash
docker compose --env-file .env.remote.models -f compose.yaml -f compose.remote.models.yaml down
```

Then stop/shutdown the cloud instance from provider control panel.
