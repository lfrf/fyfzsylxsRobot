#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

A22_CODE="${A22_CODE:-$REPO_ROOT}"
A22_ENV_ROOT="${A22_ENV_ROOT:-/root/autodl-tmp/a22/.uv_envs}"
A22_MODEL_ROOT="${A22_MODEL_ROOT:-/root/autodl-tmp/a22/models}"
A22_TMP_ROOT="${A22_TMP_ROOT:-/root/autodl-tmp/a22/tmp}"
A22_LOG_ROOT="${A22_LOG_ROOT:-/root/autodl-tmp/a22/logs}"
PYTHON_BIN="${PYTHON_BIN:-/usr/bin/python3.11}"
WRITE_ENV_SH="${WRITE_ENV_SH:-true}"
ENV_SH_PATH="${ENV_SH_PATH:-/root/autodl-tmp/a22/env.sh}"

SERVICES=(
  qwen-server
  speech-service
  vision-service
  avatar-service
  orchestrator
)

usage() {
  cat <<'EOF'
Usage:
  ./scripts/remote/bootstrap_remote_env.sh [options]

Options:
  --python BIN            Python interpreter used by uv venv (default: /usr/bin/python3.11)
  --env-root DIR          Target uv env root (default: /root/autodl-tmp/a22/.uv_envs)
  --code-root DIR         Repo root containing remote/* services
  --model-root DIR        Model root written to env.sh template
  --tmp-root DIR          TMP root written to env.sh template
  --log-root DIR          LOG root written to env.sh template
  --env-sh PATH           env.sh output path (default: /root/autodl-tmp/a22/env.sh)
  --no-write-env-sh       Do not create/update env.sh
  -h, --help              Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --python)
      PYTHON_BIN="$2"
      shift 2
      ;;
    --env-root)
      A22_ENV_ROOT="$2"
      shift 2
      ;;
    --code-root)
      A22_CODE="$2"
      shift 2
      ;;
    --model-root)
      A22_MODEL_ROOT="$2"
      shift 2
      ;;
    --tmp-root)
      A22_TMP_ROOT="$2"
      shift 2
      ;;
    --log-root)
      A22_LOG_ROOT="$2"
      shift 2
      ;;
    --env-sh)
      ENV_SH_PATH="$2"
      shift 2
      ;;
    --no-write-env-sh)
      WRITE_ENV_SH="false"
      shift
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

require_cmd() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "[error] command not found: $cmd" >&2
    exit 1
  fi
}

require_cmd uv
require_cmd tmux
require_cmd curl
require_cmd pkill

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "[error] python interpreter not executable: $PYTHON_BIN" >&2
  exit 1
fi

for svc in "${SERVICES[@]}"; do
  if [[ ! -f "$A22_CODE/remote/$svc/requirements.txt" ]]; then
    echo "[error] missing requirements.txt for service: $svc" >&2
    echo "        expected: $A22_CODE/remote/$svc/requirements.txt" >&2
    exit 1
  fi
done

mkdir -p "$A22_ENV_ROOT" "$A22_TMP_ROOT" "$A22_LOG_ROOT"

for svc in "${SERVICES[@]}"; do
  env_dir="$A22_ENV_ROOT/$svc"
  req_file="$A22_CODE/remote/$svc/requirements.txt"
  py_in_env="$env_dir/bin/python"

  if [[ ! -x "$py_in_env" ]]; then
    echo "[info] creating env: $env_dir"
    uv venv --python "$PYTHON_BIN" "$env_dir"
  else
    echo "[info] reusing env: $env_dir"
  fi

  echo "[info] installing dependencies for $svc ..."
  "$py_in_env" -m pip install --upgrade pip setuptools wheel
  "$py_in_env" -m pip install -r "$req_file"
done

if [[ ! -x "$A22_ENV_ROOT/soulx-full/bin/python" ]]; then
  echo "[warn] soulx runtime env missing: $A22_ENV_ROOT/soulx-full/bin/python"
  echo "[warn] start_remote_stack_tmux.sh requires SOULX_PYTHON for avatar video rendering."
fi

if [[ "$WRITE_ENV_SH" == "true" ]]; then
  mkdir -p "$(dirname "$ENV_SH_PATH")"
  cat >"$ENV_SH_PATH" <<EOF
#!/usr/bin/env bash
export A22_CODE="${A22_CODE}"
export A22_ENV_ROOT="${A22_ENV_ROOT}"
export A22_MODEL_ROOT="${A22_MODEL_ROOT}"
export A22_TMP_ROOT="${A22_TMP_ROOT}"
export A22_LOG_ROOT="${A22_LOG_ROOT}"
EOF
  chmod +x "$ENV_SH_PATH"
  echo "[ok] wrote env file: $ENV_SH_PATH"
fi

echo "[ok] bootstrap completed."
echo "[hint] next step: ./scripts/remote/preflight_models.sh --download-missing"
