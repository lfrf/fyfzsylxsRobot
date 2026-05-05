#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

VENV_DIR="${VENV_DIR:-$ROOT_DIR/.venv}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
RECREATE="${RECREATE:-1}"

log() {
  echo "[setup-venv] $*"
}

warn() {
  echo "[setup-venv][warn] $*" >&2
}

if [[ "$RECREATE" == "1" && -d "$VENV_DIR" ]]; then
  log "removing existing venv: $VENV_DIR"
  rm -rf "$VENV_DIR"
fi

if [[ ! -d "$VENV_DIR" ]]; then
  log "creating venv: $VENV_DIR"
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

log "python: $(python --version)"
log "pip: $(pip --version)"

log "upgrading pip tooling"
pip install --upgrade pip setuptools wheel

log "installing python packages"
pip install \
  numpy \
  opencv-python \
  picamera2 \
  pydantic \
  httpx \
  fastapi \
  uvicorn \
  pytest \
  mediapipe \
  soundfile \
  librosa \
  pyyaml

log "verifying imports"
python - <<'PY'
import sys
print("python=", sys.executable)
import numpy
import cv2
import picamera2
import libcamera
import pydantic
import httpx
import fastapi
import uvicorn
print("numpy ok", numpy.__version__)
print("cv2 ok", cv2.__version__)
print("picamera2 ok")
print("libcamera ok")
print("pydantic ok")
print("httpx ok")
print("fastapi ok")
print("uvicorn ok")
PY

log "done"
log "activate with: source \"$VENV_DIR/bin/activate\""
log "test camera probe with: python -m raspirobot.scripts.camera_capture_probe --frames 20"
