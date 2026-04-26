#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

cd "$REPO_ROOT"

docker compose -f compose.yaml -f compose.robot.yaml up -d edge-backend robot-runtime
docker compose -f compose.yaml -f compose.robot.yaml ps

echo "[ok] robot local stack started"
echo "[hint] health checks:"
echo "  curl -s http://127.0.0.1:8000/health"
echo "  curl -s http://127.0.0.1:18100/health"
