#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

A22_CODE="${A22_CODE:-$REPO_ROOT}"
A22_ENV_ROOT="${A22_ENV_ROOT:-/root/autodl-tmp/a22/.uv_envs}"
A22_MODEL_ROOT="${A22_MODEL_ROOT:-/root/autodl-tmp/a22/models}"
DOWNLOAD_MISSING="false"
DOWNLOADER_PYTHON="${DOWNLOADER_PYTHON:-}"

QWEN_LLM_REPO_ID="${QWEN_LLM_REPO_ID:-Qwen/Qwen2.5-7B-Instruct}"
QWEN_ASR_REPO_ID="${QWEN_ASR_REPO_ID:-Qwen/Qwen3-ASR-1.7B}"
QWEN_VL_REPO_ID="${QWEN_VL_REPO_ID:-Qwen/Qwen2.5-VL-7B-Instruct}"
EMOTION2VEC_REPO_ID="${EMOTION2VEC_REPO_ID:-emotion2vec/emotion2vec_plus_base}"
COSYVOICE_300M_REPO_ID="${COSYVOICE_300M_REPO_ID:-FunAudioLLM/CosyVoice-300M-Instruct}"
WAV2VEC_REPO_ID="${WAV2VEC_REPO_ID:-facebook/wav2vec2-base-960h}"
SOULX_ROOT_REPO_ID="${SOULX_ROOT_REPO_ID:-Kedreamix/SoulX-FlashHead}"
SOULX_CKPT_REPO_ID="${SOULX_CKPT_REPO_ID:-Kedreamix/SoulX-FlashHead-1_3B}"
COSYVOICE_REPO_URL="${COSYVOICE_REPO_URL:-https://github.com/FunAudioLLM/CosyVoice.git}"

REQUIRED_MODELS=(
  "Qwen2.5-7B-Instruct"
  "Qwen3-ASR-1.7B"
  "Qwen2.5-VL-7B-Instruct"
  "emotion2vec_plus_base"
  "hsemotion"
  "CosyVoice-300M-Instruct"
  "CosyVoice"
  "SoulX-FlashHead"
  "SoulX-FlashHead-1_3B"
  "wav2vec2-base-960h"
)

usage() {
  cat <<'EOF'
Usage:
  ./scripts/remote/preflight_models.sh [options]

Options:
  --model-root DIR          Model root directory (default: /root/autodl-tmp/a22/models)
  --download-missing        Try downloading missing models automatically
  --python BIN              Python executable used for HuggingFace downloads
  -h, --help                Show this help

Environment overrides:
  QWEN_LLM_REPO_ID, QWEN_ASR_REPO_ID, QWEN_VL_REPO_ID
  EMOTION2VEC_REPO_ID, COSYVOICE_300M_REPO_ID, WAV2VEC_REPO_ID
  SOULX_ROOT_REPO_ID, SOULX_CKPT_REPO_ID, COSYVOICE_REPO_URL
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --model-root)
      A22_MODEL_ROOT="$2"
      shift 2
      ;;
    --download-missing)
      DOWNLOAD_MISSING="true"
      shift
      ;;
    --python)
      DOWNLOADER_PYTHON="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "[error] unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

resolve_downloader_python() {
  if [[ -n "$DOWNLOADER_PYTHON" ]]; then
    if [[ ! -x "$DOWNLOADER_PYTHON" ]]; then
      echo "[error] downloader python not executable: $DOWNLOADER_PYTHON" >&2
      exit 1
    fi
    return 0
  fi

  if [[ -x "$A22_ENV_ROOT/qwen-server/bin/python" ]]; then
    DOWNLOADER_PYTHON="$A22_ENV_ROOT/qwen-server/bin/python"
    return 0
  fi
  if command -v python3 >/dev/null 2>&1; then
    DOWNLOADER_PYTHON="$(command -v python3)"
    return 0
  fi
  if command -v python >/dev/null 2>&1; then
    DOWNLOADER_PYTHON="$(command -v python)"
    return 0
  fi
  echo "[error] no python interpreter available for model download." >&2
  exit 1
}

ensure_hf_hub() {
  if "$DOWNLOADER_PYTHON" -c "import huggingface_hub" >/dev/null 2>&1; then
    return 0
  fi
  echo "[info] installing huggingface_hub for downloader python ..."
  "$DOWNLOADER_PYTHON" -m pip install --upgrade huggingface_hub
}

snapshot_download() {
  local repo_id="$1"
  local target_dir="$2"
  ensure_hf_hub
  mkdir -p "$target_dir"
  "$DOWNLOADER_PYTHON" - "$repo_id" "$target_dir" <<'PY'
import sys
from huggingface_hub import snapshot_download

repo = sys.argv[1]
target = sys.argv[2]
snapshot_download(
    repo_id=repo,
    local_dir=target,
    local_dir_use_symlinks=False,
    resume_download=True,
)
print(f"[ok] downloaded {repo} -> {target}")
PY
}

directory_ready() {
  local dir="$1"
  [[ -d "$dir" ]] || return 1
  [[ -n "$(find "$dir" -mindepth 1 -maxdepth 1 2>/dev/null | head -n 1)" ]] || return 1
  return 0
}

download_hsemotion_cache() {
  local target_dir="$1"
  local script_path="$A22_CODE/remote/vision-service/scripts/prefetch_face_emotion_model.py"
  local python_bin=""

  if [[ -x "$A22_ENV_ROOT/vision-service/bin/python" ]]; then
    python_bin="$A22_ENV_ROOT/vision-service/bin/python"
  else
    python_bin="$DOWNLOADER_PYTHON"
  fi

  if [[ ! -f "$script_path" ]]; then
    echo "[warn] hsemotion prefetch script not found: $script_path"
    return 1
  fi

  mkdir -p "$target_dir"
  if TORCH_HOME="$target_dir" "$python_bin" "$script_path" --model-name enet_b2_7 --device cpu; then
    return 0
  fi

  echo "[warn] hsemotion prefetch failed once, retrying after dependency install ..."
  "$python_bin" -m pip install --upgrade hsemotion timm opencv-python-headless
  TORCH_HOME="$target_dir" "$python_bin" "$script_path" --model-name enet_b2_7 --device cpu
}

download_emotion2vec() {
  local target_dir="$1"
  local script_path="$A22_CODE/remote/speech-service/scripts/download_emotion2vec_model.py"
  local python_bin=""

  if [[ -x "$A22_ENV_ROOT/speech-service/bin/python" ]]; then
    python_bin="$A22_ENV_ROOT/speech-service/bin/python"
  else
    python_bin="$DOWNLOADER_PYTHON"
  fi

  if [[ -f "$script_path" ]]; then
    "$python_bin" "$script_path" --repo-id "$EMOTION2VEC_REPO_ID" --local-dir "$target_dir"
    return 0
  fi

  snapshot_download "$EMOTION2VEC_REPO_ID" "$target_dir"
}

download_cosyvoice_repo() {
  local target_dir="$1"
  if ! command -v git >/dev/null 2>&1; then
    echo "[error] git not found, cannot clone CosyVoice repo." >&2
    return 1
  fi
  git clone --depth=1 "$COSYVOICE_REPO_URL" "$target_dir"
}

download_model() {
  local model_name="$1"
  local target_dir="$A22_MODEL_ROOT/$model_name"

  case "$model_name" in
    "emotion2vec_plus_base")
      download_emotion2vec "$target_dir"
      ;;
    "hsemotion")
      download_hsemotion_cache "$target_dir"
      ;;
    "CosyVoice")
      download_cosyvoice_repo "$target_dir"
      ;;
    "Qwen2.5-7B-Instruct")
      snapshot_download "$QWEN_LLM_REPO_ID" "$target_dir"
      ;;
    "Qwen3-ASR-1.7B")
      snapshot_download "$QWEN_ASR_REPO_ID" "$target_dir"
      ;;
    "Qwen2.5-VL-7B-Instruct")
      snapshot_download "$QWEN_VL_REPO_ID" "$target_dir"
      ;;
    "CosyVoice-300M-Instruct")
      snapshot_download "$COSYVOICE_300M_REPO_ID" "$target_dir"
      ;;
    "wav2vec2-base-960h")
      snapshot_download "$WAV2VEC_REPO_ID" "$target_dir"
      ;;
    "SoulX-FlashHead")
      snapshot_download "$SOULX_ROOT_REPO_ID" "$target_dir"
      ;;
    "SoulX-FlashHead-1_3B")
      snapshot_download "$SOULX_CKPT_REPO_ID" "$target_dir"
      ;;
    *)
      echo "[error] unsupported model name: $model_name" >&2
      return 1
      ;;
  esac
}

mkdir -p "$A22_MODEL_ROOT"

echo "[info] model root: $A22_MODEL_ROOT"
echo "[info] required model directories:"
for model_name in "${REQUIRED_MODELS[@]}"; do
  echo "  - $model_name"
done

missing_models=()
for model_name in "${REQUIRED_MODELS[@]}"; do
  if directory_ready "$A22_MODEL_ROOT/$model_name"; then
    echo "[ok] $model_name"
  else
    echo "[missing] $model_name"
    missing_models+=("$model_name")
  fi
done

if [[ "${#missing_models[@]}" -eq 0 ]]; then
  echo "[ok] all required models are present."
  exit 0
fi

if [[ "$DOWNLOAD_MISSING" != "true" ]]; then
  echo "[error] missing required models."
  echo "[hint] re-run with --download-missing to auto-fetch missing models."
  exit 2
fi

resolve_downloader_python
echo "[info] downloader python: $DOWNLOADER_PYTHON"

download_failed=()
for model_name in "${missing_models[@]}"; do
  echo "[info] downloading: $model_name"
  if download_model "$model_name"; then
    echo "[ok] download done: $model_name"
  else
    echo "[error] download failed: $model_name"
    download_failed+=("$model_name")
  fi
done

remaining_missing=()
for model_name in "${REQUIRED_MODELS[@]}"; do
  if ! directory_ready "$A22_MODEL_ROOT/$model_name"; then
    remaining_missing+=("$model_name")
  fi
done

if [[ "${#remaining_missing[@]}" -eq 0 ]]; then
  echo "[ok] all required models are now present."
  exit 0
fi

echo "[error] model preflight still has missing items:"
for model_name in "${remaining_missing[@]}"; do
  echo "  - $model_name"
done

if [[ "${#download_failed[@]}" -gt 0 ]]; then
  echo "[error] automatic download failed for:"
  for model_name in "${download_failed[@]}"; do
    echo "  - $model_name"
  done
fi

exit 1
