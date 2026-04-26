# remote

Services that run on the **lab server** or other remote hosts.

## Current role

`remote/` is the server-side part of the monorepo. At the current stage it mainly hosts:

- `orchestrator/` — v0 HTTP API matching `shared/contracts/api_v1.md`

## Recommended runtime strategy

At this stage, the remote host should support two deployment modes:

1. `uv + .venv + uvicorn`  
   This is the current fallback plan when the remote user does not have Docker daemon access.

2. `docker compose`  
   Keep `compose.remote.yaml` as the future deployment target once Docker permission is available.

## Recommended future layout

```text
remote/
├─ README.md
├─ orchestrator/
│  ├─ app.py
│  ├─ pyproject.toml
│  ├─ requirements.txt
│  ├─ .python-version
│  └─ README.md
├─ llm-service/
├─ rag-service/
├─ tts-service/
└─ state-estimator/
```

## Where the virtual environment should live

Do **not** put one shared `.venv` under `remote/` root for all future services.

For the current project stage, the best choice is:

- `remote/orchestrator/.venv`

Reason:

- each remote service may have different dependencies later
- service-level isolation is clearer
- it is easier to migrate each service back to Docker later

See `remote/orchestrator/README.md` for concrete setup steps.
