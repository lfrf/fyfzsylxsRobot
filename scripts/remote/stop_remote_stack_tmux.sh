#!/usr/bin/env bash
set -euo pipefail

for session_name in orchestrator avatar vision speech qwen; do
  tmux kill-session -t "$session_name" 2>/dev/null || true
done

echo "[ok] stopped tmux sessions: orchestrator avatar vision speech qwen"
