# AutoDL Frontend-Remote Link Runbook

## 1. Scope

This runbook is for the current AutoDL layout:

- Code root: `/root/autodl-tmp/a22/code/FuChuangSai_A22`
- Model root: `/root/autodl-tmp/a22/models`
- Goal: frontend sends `/chat` to remote orchestrator and plays returned `reply.mp4` (or stream chunk manifest).

## 2. Pull latest code on remote

```bash
cd /root/autodl-tmp/a22/code/FuChuangSai_A22
git pull
```

## 3. Start/stop remote stack with tmux

```bash
cd /root/autodl-tmp/a22/code/FuChuangSai_A22
chmod +x scripts/remote/*.sh
./scripts/remote/stop_remote_stack_tmux.sh
./scripts/remote/start_remote_stack_tmux.sh
```

If you only want to restart avatar-service (keeping other 4 services untouched):

```bash
cd /root/autodl-tmp/a22/code/FuChuangSai_A22
chmod +x scripts/remote/*.sh
./scripts/remote/restart_avatar_service_soulx_full.sh
```

The start script launches:

- `qwen` on `127.0.0.1:8000`
- `speech` on `127.0.0.1:19100`
- `vision` on `127.0.0.1:19200`
- `avatar` on `127.0.0.1:19300`
- `orchestrator` on `127.0.0.1:19000`

Default avatar settings in the script:

- `AVATAR_RENDERER_BACKEND=soulxflashhead`
- `AVATAR_ENV_NAME=avatar-service`
- `SOULX_PYTHON=/root/autodl-tmp/a22/.uv_envs/soulx-full/bin/python`
- `SOULX_INFER_SCRIPT=generate_video.py`
- `SOULX_COMMAND_TEMPLATE=<soulx-full python + generate_video.py>`
- `TTS_MODE=cosyvoice_300m_instruct`
- `TTS_MODEL=/root/autodl-tmp/a22/models/CosyVoice-300M-Instruct`
- `AVATAR_SERVICE_TIMEOUT_SECONDS=600` (to avoid orchestrator fallback when SoulX render is slow)

If your machine uses a different avatar env (for example `avatar-service-soulx`), run:

```bash
export AVATAR_ENV_NAME=avatar-service-soulx
./scripts/remote/start_remote_stack_tmux.sh
```

## 4. Health checks on remote

```bash
curl -s http://127.0.0.1:8000/v1/models | python -m json.tool
curl -s http://127.0.0.1:19100/health | python -m json.tool
curl -s http://127.0.0.1:19200/health | python -m json.tool
curl -s http://127.0.0.1:19300/health | python -m json.tool
curl -s http://127.0.0.1:19000/health | python -m json.tool
```

## 5. Frontend configuration on local machine

Set `local/frontend/.env.local`:

```env
VITE_USE_DIRECT_API=false
VITE_API_PROXY_TARGET=https://<your-autodl-public-domain>:8443
VITE_AVATAR_SESSION_ID=demo_s1
VITE_AVATAR_STREAM_ID=demo_stream_1
```

Then start frontend:

```bash
cd local/frontend
npm install
npm run dev -- --host 0.0.0.0 --port 3000
```

## 6. End-to-end check

First verify gateway to orchestrator:

```bash
curl -k https://<your-autodl-public-domain>:8443/health
```

Then send one text turn:

```bash
curl -k -X POST "https://<your-autodl-public-domain>:8443/chat" \
  -H "Content-Type: application/json" \
  -d '{"session_id":"demo_s1","turn_id":1,"user_text":"Please give me one short encouragement.","input_type":"text"}'
```

Expected in response:

- `reply_text` is non-empty
- `reply_video_url` or `reply_video_stream_url` is non-empty

If this is true, frontend can play returned video through `/media/...`.
