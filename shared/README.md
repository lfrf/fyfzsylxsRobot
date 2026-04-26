# shared

Cross-cutting artifacts used by both **local** and **remote** code.

## contracts

- `api_v1.md` — HTTP JSON contract between edge and orchestrator (v0).
- `chat_request.example.json` — Example request body for `POST /chat`.
- `chat_response.example.json` — Example success response for `POST /chat`.

Keep definitions in one place so local and remote implementations stay aligned.
