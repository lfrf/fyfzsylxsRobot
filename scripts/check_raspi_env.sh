#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "[check] working directory: $ROOT_DIR"

if [[ -d ".venv" ]]; then
  echo "[check] .venv: present"
else
  echo "[warn] .venv: missing; run bash scripts/setup_raspi_venv.sh"
fi

if [[ -x ".venv/bin/python" ]]; then
  PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
elif command -v python3.11 >/dev/null 2>&1; then
  PYTHON_BIN="$(command -v python3.11)"
else
  PYTHON_BIN="$(command -v python3)"
fi

echo "[check] python: $($PYTHON_BIN --version)"

if command -v arecord >/dev/null 2>&1; then
  echo "[check] arecord: $(command -v arecord)"
else
  echo "[warn] arecord not found; install alsa-utils on Raspberry Pi."
fi

if command -v aplay >/dev/null 2>&1; then
  echo "[check] aplay: $(command -v aplay)"
else
  echo "[warn] aplay not found; install alsa-utils on Raspberry Pi."
fi

echo "[check] ROBOT_REMOTE_BASE_URL=${ROBOT_REMOTE_BASE_URL:-<unset>}"
echo "[check] ROBOT_AUDIO_CAPTURE_DEVICE=${ROBOT_AUDIO_CAPTURE_DEVICE:-<unset>}"
echo "[check] ROBOT_AUDIO_PLAYBACK_DEVICE=${ROBOT_AUDIO_PLAYBACK_DEVICE:-<unset>}"
echo "[check] ROBOT_AUDIO_SAMPLE_RATE=${ROBOT_AUDIO_SAMPLE_RATE:-<unset>}"
echo "[check] ROBOT_AUDIO_CHANNELS=${ROBOT_AUDIO_CHANNELS:-<unset>}"
echo "[check] ROBOT_EYES_PROVIDER=${ROBOT_EYES_PROVIDER:-<unset>}"
echo "[check] ROBOT_EYES_ASSETS_DIR=${ROBOT_EYES_ASSETS_DIR:-<unset>}"
echo "[check] ROBOT_EYES_DC_GPIO=${ROBOT_EYES_DC_GPIO:-<unset>}"
echo "[check] ROBOT_EYES_RST_GPIO=${ROBOT_EYES_RST_GPIO:-<unset>}"
echo "[check] ROBOT_EYES_LEFT_CS=${ROBOT_EYES_LEFT_CS:-<unset>}"
echo "[check] ROBOT_EYES_RIGHT_CS=${ROBOT_EYES_RIGHT_CS:-<unset>}"

if [[ -e "/dev/spidev0.0" || -e "/dev/spidev0.1" ]]; then
  echo "[check] spidev: present"
else
  echo "[warn] spidev not found; enable SPI in raspi-config and reboot."
fi

PYTHONPATH="$ROOT_DIR" "$PYTHON_BIN" - <<'PY'
import raspirobot
from raspirobot.config import load_settings

settings = load_settings()
print("[check] import raspirobot: ok")
print("[check] remote_base_url:", settings.remote_base_url)
print("[check] audio_capture_provider:", settings.audio_capture_provider)
print("[check] audio_output_provider:", settings.audio_output_provider)
print("[check] audio_sample_rate:", settings.audio_sample_rate)
print("[check] audio_channels:", settings.audio_channels)
PY

if command -v arecord >/dev/null 2>&1; then
  echo "[check] capture devices:"
  arecord -l || true
fi

if command -v aplay >/dev/null 2>&1; then
  echo "[check] playback devices:"
  aplay -l || true
fi
