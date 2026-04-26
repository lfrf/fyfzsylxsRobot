#!/usr/bin/env bash
set -euo pipefail

if [ -f /root/autodl-tmp/a22/env.sh ]; then
  # shellcheck disable=SC1091
  source /root/autodl-tmp/a22/env.sh
fi

export A22_CODE="${A22_CODE:-/root/autodl-tmp/a22/code/FuChuangSai_A22}"
export A22_ENV_ROOT="${A22_ENV_ROOT:-/root/autodl-tmp/a22/.uv_envs}"
export A22_MODEL_ROOT="${A22_MODEL_ROOT:-/root/autodl-tmp/a22/models}"
export A22_LOG_ROOT="${A22_LOG_ROOT:-/root/autodl-tmp/a22/logs}"
export A22_TMP_ROOT="${A22_TMP_ROOT:-/root/autodl-tmp/a22/tmp}"

export AVATAR_ENV_NAME="${AVATAR_ENV_NAME:-avatar-service}"
export AVATAR_HOST="${AVATAR_HOST:-127.0.0.1}"
export AVATAR_PORT="${AVATAR_PORT:-19300}"

export SOULX_ROOT="${SOULX_ROOT:-$A22_MODEL_ROOT/SoulX-FlashHead}"
export SOULX_INFER_SCRIPT="${SOULX_INFER_SCRIPT:-generate_video.py}"
export SOULX_REF_IMAGE_PATH="${SOULX_REF_IMAGE_PATH:-$A22_MODEL_ROOT/SoulX-FlashHead/examples/girl.png}"
export SOULX_PYTHON="${SOULX_PYTHON:-$A22_ENV_ROOT/soulx-full/bin/python}"
export SOULX_CKPT_DIR="${SOULX_CKPT_DIR:-$A22_MODEL_ROOT/SoulX-FlashHead-1_3B}"
export SOULX_WAV2VEC_DIR="${SOULX_WAV2VEC_DIR:-$A22_MODEL_ROOT/wav2vec2-base-960h}"
export SOULX_ASYNC_RENDER="${SOULX_ASYNC_RENDER:-false}"
DEFAULT_SOULX_COMMAND_TEMPLATE="$SOULX_PYTHON {infer_script} --ckpt_dir $SOULX_CKPT_DIR --wav2vec_dir $SOULX_WAV2VEC_DIR --model_type lite --cond_image {ref_image_path} --audio_path {audio_path} --audio_encode_mode stream --save_file {output_path}"
export SOULX_COMMAND_TEMPLATE="${SOULX_COMMAND_TEMPLATE:-$DEFAULT_SOULX_COMMAND_TEMPLATE}"

export TTS_MODE="${TTS_MODE:-cosyvoice_300m_instruct}"
export TTS_MODEL="${TTS_MODEL:-$A22_MODEL_ROOT/CosyVoice-300M-Instruct}"
export TTS_REPO_PATH="${TTS_REPO_PATH:-$A22_MODEL_ROOT/CosyVoice}"
# Default to fixed female speaker unless explicitly overridden.
export TTS_SPEAKER_ID="${TTS_SPEAKER_ID:-$'\u4e2d\u6587\u5973'}"
export TTS_DEVICE="${TTS_DEVICE:-cuda:0}"
export PYTHONPATH="${PYTHONPATH:-$TTS_REPO_PATH:$TTS_REPO_PATH/third_party/Matcha-TTS}"

if [ ! -x "$A22_ENV_ROOT/$AVATAR_ENV_NAME/bin/python" ]; then
  echo "[error] missing avatar env: $A22_ENV_ROOT/$AVATAR_ENV_NAME" >&2
  exit 1
fi
if [ ! -x "$SOULX_PYTHON" ]; then
  echo "[error] missing soulx python: $SOULX_PYTHON" >&2
  exit 1
fi

mkdir -p "$A22_LOG_ROOT" "$A22_TMP_ROOT/avatar"

tmux kill-session -t avatar 2>/dev/null || true
source "$A22_ENV_ROOT/$AVATAR_ENV_NAME/bin/activate"
pkill -f "uvicorn app:app.*--port $AVATAR_PORT" 2>/dev/null || true

cd "$A22_CODE/remote/avatar-service"
nohup python -m uvicorn app:app --host "$AVATAR_HOST" --port "$AVATAR_PORT" \
  > "$A22_LOG_ROOT/avatar-service.log" 2>&1 < /dev/null &

for i in $(seq 1 40); do
  if curl -fsS "http://$AVATAR_HOST:$AVATAR_PORT/health" >/dev/null; then
    echo "[ok] avatar-service ready on http://$AVATAR_HOST:$AVATAR_PORT/health"
    exit 0
  fi
  sleep 1
done

echo "[error] avatar-service did not become healthy in 40s" >&2
tail -n 120 "$A22_LOG_ROOT/avatar-service.log" || true
exit 1

