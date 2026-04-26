# local

Edge-side code that runs in **WSL2 + Docker** on the developer machine.

## Contents

- `frontend/` — Web UI and client logic (Vite dev server in compose).
- `edge-backend/` — FastAPI gateway: session handling, preprocessing, forwarding to remote orchestrator, response shaping for the UI.

## Compose

Paths in `compose.local.yaml` bind:

- `./local/frontend` → `frontend` container
- `./local/edge-backend` → `edge-backend` container

Start from repository root:

```bash
docker compose -f compose.yaml -f compose.local.yaml up -d
```
