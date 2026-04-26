# orchestrator (remote skeleton)

Minimal HTTP service implementing **contract v0** (`shared/contracts/api_v1.md`).

## Runtime recommendation

Current priority:

1. use `uv + .venv + uvicorn` on the lab server
2. keep Docker as a future deployment option

This service uses Python 3.11 syntax, so the remote runtime must use **Python 3.11**.

## Required files

- `app.py` — remote HTTP service
- `pyproject.toml` — `uv` dependency and Python version requirement
- `requirements.txt` — compatibility fallback
- `.python-version` — preferred local Python version marker

## Recreate the remote uv environment

If an old environment already exists, delete it first and recreate it with Python 3.11.

```bash
cd remote/orchestrator
rm -rf .venv
uv python install 3.11
uv venv --python 3.11 .venv
source .venv/bin/activate
uv sync
```

If `uv python install 3.11` is unavailable on the server, use an existing Python 3.11 binary instead:

```bash
cd remote/orchestrator
rm -rf .venv
uv venv --python /usr/bin/python3.11 .venv
source .venv/bin/activate
uv sync
```

## Run without Docker (lab server)

```bash
cd remote/orchestrator
source .venv/bin/activate
uv run uvicorn app:app --host 127.0.0.1 --port 19000
```

run llm
python -m vllm.entrypoints.openai.api_server   --host 127.0.0.1   --port 8000   --model /data/zifeng/siyuan/A22/models/Qwen2.5-7B-Instruct   --served-model-name Qwen2.5-7B-Instruct   --dtype auto   --gpu-memory-utilization 0.80   --trust-remote-code

Bind to `127.0.0.1` when exposing only via SSH tunnel from your laptop.

## Health check

On the remote host itself:

```bash
curl http://127.0.0.1:19000/health
curl -X POST http://127.0.0.1:19000/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id":"demo-001","turn_id":1,"user_text":"hello","input_type":"text"}'
```

## Run with Docker (future option)

From repository root:

```bash
docker compose -f compose.yaml -f compose.remote.yaml up -d orchestrator
```

## Endpoints

- `GET /health`
- `POST /chat`

See `../../shared/contracts/` for JSON shapes.


cd /home/zifeng/siyuan/A22/A22_wmzjbyGroup/remote/qwen-server
source .venv/bin/activate
CUDA_VISIBLE_DEVICES=2 vllm serve /data/zifeng/siyuan/A22/models/Qwen2.5-7B-Instruct \
  --served-model-name Qwen2.5-7B-Instruct \
  --host 127.0.0.1 \
  --port 8000 \
  --gpu-memory-utilization 0.90 \
  --max-model-len 8192


cd /home/zifeng/siyuan/A22/A22_wmzjbyGroup/remote/orchestrator
source .venv/bin/activate
export LLM_PROVIDER=qwen
export LLM_MODEL=Qwen2.5-7B-Instruct
export LLM_API_BASE=http://127.0.0.1:8000/v1
export LLM_API_KEY=EMPTY
export LLM_REQUEST_TIMEOUT_SECONDS=60
export LLM_TEMPERATURE=0.4
export LLM_MAX_TOKENS=256
uv run uvicorn app:app --host 127.0.0.1 --port 19000

ss -ltnp | grep 8000
ps -ef | grep "uvicorn app:app --host 127.0.0.1 --port 19000"