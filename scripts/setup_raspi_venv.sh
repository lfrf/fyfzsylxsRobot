#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if command -v python3.11 >/dev/null 2>&1; then
  PYTHON_BIN="$(command -v python3.11)"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="$(command -v python3)"
else
  echo "[error] python3.11 or python3 is required." >&2
  exit 1
fi

echo "[setup] using Python: $PYTHON_BIN"
"$PYTHON_BIN" -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r raspirobot/requirements.raspi.txt

cat <<'TXT'

[ok] raspirobot local venv is ready.

Next:
  source .venv/bin/activate
  bash scripts/check_raspi_env.sh
  export ROBOT_REMOTE_BASE_URL=http://127.0.0.1:29000
  export ROBOT_AUDIO_CAPTURE_DEVICE=plughw:3,0
  export ROBOT_AUDIO_PLAYBACK_DEVICE=plughw:3,0
  export ROBOT_AUDIO_SAMPLE_RATE=16000
  export ROBOT_AUDIO_CHANNELS=2
  python -m raspirobot.scripts.audio_tunnel_smoke --wav /tmp/robot_test.wav
  python -m raspirobot.scripts.live_audio_loop
TXT
