#!/usr/bin/env bash
set -euo pipefail

if [ -f /root/autodl-tmp/a22/env.sh ]; then
  # shellcheck disable=SC1091
  source /root/autodl-tmp/a22/env.sh
fi

export A22_CODE="${A22_CODE:-/root/autodl-tmp/a22/code/FuChuangSai_A22}"
export A22_MODEL_ROOT="${A22_MODEL_ROOT:-/root/autodl-tmp/a22/models}"
export A22_ENV_ROOT="${A22_ENV_ROOT:-/root/autodl-tmp/a22/.uv_envs}"
export A22_TMP_ROOT="${A22_TMP_ROOT:-/root/autodl-tmp/a22/tmp}"
export A22_LOG_ROOT="${A22_LOG_ROOT:-/root/autodl-tmp/a22/logs}"

export QWEN_CUDA_VISIBLE_DEVICES="${QWEN_CUDA_VISIBLE_DEVICES:-0}"
export SPEECH_CUDA_VISIBLE_DEVICES="${SPEECH_CUDA_VISIBLE_DEVICES:-0}"
export VISION_CUDA_VISIBLE_DEVICES="${VISION_CUDA_VISIBLE_DEVICES:-0}"

export QWEN_MODEL_PATH="${QWEN_MODEL_PATH:-$A22_MODEL_ROOT/Qwen2.5-7B-Instruct}"
export QWEN_MODEL_NAME="${QWEN_MODEL_NAME:-Qwen2.5-7B-Instruct}"
export QWEN_GPU_MEMORY_UTILIZATION="${QWEN_GPU_MEMORY_UTILIZATION:-0.28}"
export QWEN_MAX_MODEL_LEN="${QWEN_MAX_MODEL_LEN:-4096}"
export QWEN_MAX_NUM_SEQS="${QWEN_MAX_NUM_SEQS:-2}"

export ASR_MODEL_PATH="${ASR_MODEL_PATH:-$A22_MODEL_ROOT/Qwen3-ASR-1.7B}"
export SER_ENABLED="${SER_ENABLED:-true}"
export SER_PROVIDER="${SER_PROVIDER:-emotion2vec_plus_base}"
export SER_MODEL_PATH="${SER_MODEL_PATH:-$A22_MODEL_ROOT/emotion2vec_plus_base}"
export SER_DEVICE="${SER_DEVICE:-cuda:0}"
export SER_HUB="${SER_HUB:-ms}"
export SER_TOP_K="${SER_TOP_K:-3}"
export SER_MIN_CONFIDENCE="${SER_MIN_CONFIDENCE:-0.2}"
export SER_WARMUP_ENABLED="${SER_WARMUP_ENABLED:-true}"
export VISION_MODEL_PATH="${VISION_MODEL_PATH:-$A22_MODEL_ROOT/Qwen2.5-VL-7B-Instruct}"
export FER_ENABLED="${FER_ENABLED:-true}"
export FER_PROVIDER="${FER_PROVIDER:-hsemotion}"
export FER_MODEL_NAME="${FER_MODEL_NAME:-enet_b2_7}"
export FER_DEVICE="${FER_DEVICE:-cpu}"
export FER_DETECTOR="${FER_DETECTOR:-haar}"
export FER_MAX_FRAMES="${FER_MAX_FRAMES:-4}"
export FER_MIN_CONFIDENCE="${FER_MIN_CONFIDENCE:-0.2}"
export FER_WARMUP_ENABLED="${FER_WARMUP_ENABLED:-true}"
export FER_FORCE_NO_WEIGHTS_ONLY_LOAD="${FER_FORCE_NO_WEIGHTS_ONLY_LOAD:-true}"
export HSEMOTION_CACHE_DIR="${HSEMOTION_CACHE_DIR:-$A22_MODEL_ROOT/hsemotion}"

for env_name in qwen-server speech-service vision-service orchestrator; do
  if [ ! -x "$A22_ENV_ROOT/$env_name/bin/python" ]; then
    echo "[error] missing uv environment: $A22_ENV_ROOT/$env_name" >&2
    exit 1
  fi
done

mkdir -p "$A22_TMP_ROOT/speech" "$A22_TMP_ROOT/vision" "$A22_LOG_ROOT"

for session_name in qwen speech vision orchestrator; do
  tmux kill-session -t "$session_name" 2>/dev/null || true
done

# Clear stale non-tmux processes that may still occupy these ports.
pkill -f "vllm.entrypoints.openai.api_server.*--port 8000" 2>/dev/null || true
pkill -f "uvicorn app:app.*--port 19100" 2>/dev/null || true
pkill -f "uvicorn app:app.*--port 19200" 2>/dev/null || true
pkill -f "uvicorn app:app.*--port 19000" 2>/dev/null || true

tmux new-session -d -s qwen "bash -lc '
set -euo pipefail
if [ -f /root/autodl-tmp/a22/env.sh ]; then
  source /root/autodl-tmp/a22/env.sh
fi
source \"$A22_ENV_ROOT/qwen-server/bin/activate\"
cd \"$A22_CODE/remote/qwen-server\"
export CUDA_VISIBLE_DEVICES=\"$QWEN_CUDA_VISIBLE_DEVICES\"
exec python -m vllm.entrypoints.openai.api_server \
  --host 127.0.0.1 --port 8000 \
  --model \"$QWEN_MODEL_PATH\" \
  --served-model-name \"$QWEN_MODEL_NAME\" \
  --dtype auto --gpu-memory-utilization \"$QWEN_GPU_MEMORY_UTILIZATION\" \
  --max-model-len \"$QWEN_MAX_MODEL_LEN\" --max-num-seqs \"$QWEN_MAX_NUM_SEQS\" --trust-remote-code
'"

tmux new-session -d -s speech "bash -lc '
set -euo pipefail
if [ -f /root/autodl-tmp/a22/env.sh ]; then
  source /root/autodl-tmp/a22/env.sh
fi
source \"$A22_ENV_ROOT/speech-service/bin/activate\"
cd \"$A22_CODE/remote/speech-service\"
export CUDA_VISIBLE_DEVICES=\"$SPEECH_CUDA_VISIBLE_DEVICES\"
export TMP_DIR=\"$A22_TMP_ROOT/speech\"
export ASR_PROVIDER=qwen3_asr
export ASR_MODEL=\"$ASR_MODEL_PATH\"
export ASR_LANGUAGE=Chinese
export ASR_DEVICE=cuda:0
export ASR_WARMUP_ENABLED=false
export SER_ENABLED=\"$SER_ENABLED\"
export SER_PROVIDER=\"$SER_PROVIDER\"
export SER_MODEL=\"$SER_MODEL_PATH\"
export SER_DEVICE=\"$SER_DEVICE\"
export SER_HUB=\"$SER_HUB\"
export SER_TOP_K=\"$SER_TOP_K\"
export SER_MIN_CONFIDENCE=\"$SER_MIN_CONFIDENCE\"
export SER_WARMUP_ENABLED=\"$SER_WARMUP_ENABLED\"
export QWEN_ASR_USE_FLASH_ATTN=true
export QWEN_ASR_USE_ITN=false
exec python -m uvicorn app:app --host 127.0.0.1 --port 19100
'"

tmux new-session -d -s vision "bash -lc '
set -euo pipefail
if [ -f /root/autodl-tmp/a22/env.sh ]; then
  source /root/autodl-tmp/a22/env.sh
fi
source \"$A22_ENV_ROOT/vision-service/bin/activate\"
cd \"$A22_CODE/remote/vision-service\"
export CUDA_VISIBLE_DEVICES=\"$VISION_CUDA_VISIBLE_DEVICES\"
export TMP_DIR=\"$A22_TMP_ROOT/vision\"
export VISION_EXTRACTOR_MODE=qwen2_5_vl
export VISION_MODEL=\"$VISION_MODEL_PATH\"
export VISION_DEVICE=cuda:0
export VISION_DTYPE=float16
export VISION_WARMUP_ENABLED=false
export FER_ENABLED=\"$FER_ENABLED\"
export FER_PROVIDER=\"$FER_PROVIDER\"
export FER_MODEL_NAME=\"$FER_MODEL_NAME\"
export FER_DEVICE=\"$FER_DEVICE\"
export FER_DETECTOR=\"$FER_DETECTOR\"
export FER_MAX_FRAMES=\"$FER_MAX_FRAMES\"
export FER_MIN_CONFIDENCE=\"$FER_MIN_CONFIDENCE\"
export FER_WARMUP_ENABLED=\"$FER_WARMUP_ENABLED\"
export FER_FORCE_NO_WEIGHTS_ONLY_LOAD=\"$FER_FORCE_NO_WEIGHTS_ONLY_LOAD\"
export TORCH_HOME=\"$HSEMOTION_CACHE_DIR\"
exec python -m uvicorn app:app --host 127.0.0.1 --port 19200
'"

tmux new-session -d -s orchestrator "bash -lc '
set -euo pipefail
if [ -f /root/autodl-tmp/a22/env.sh ]; then
  source /root/autodl-tmp/a22/env.sh
fi
source \"$A22_ENV_ROOT/orchestrator/bin/activate\"
cd \"$A22_CODE/remote/orchestrator\"
export LLM_PROVIDER=qwen
export LLM_MODEL=\"$QWEN_MODEL_NAME\"
export LLM_API_BASE=http://127.0.0.1:8000/v1
export LLM_API_KEY=EMPTY
export SPEECH_SERVICE_ENABLED=true
export SPEECH_SERVICE_BASE=http://127.0.0.1:19100
export VISION_SERVICE_ENABLED=true
export VISION_SERVICE_BASE=http://127.0.0.1:19200
export EMOTION_SERVICE_ENABLED=false
exec python -m uvicorn app:app --host 127.0.0.1 --port 19000
'"

echo "[ok] tmux sessions started:"
tmux ls | grep -E '^(qwen|speech|vision|orchestrator):'
echo "[hint] check health: curl -s http://127.0.0.1:19000/health | python -m json.tool"
