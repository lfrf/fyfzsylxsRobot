# Emotion Models Setup (Remote Server)

This runbook assumes the code is modified locally and pushed to GitHub first, then the remote server pulls the latest commit.

## 1. Pull latest code on remote server

```bash
cd /root/autodl-tmp/a22/code/FuChuangSai_A22
git pull
```

## 2. Speech emotion model (`emotion2vec_plus_base`)

### 2.1 Sync dependencies

```bash
cd /root/autodl-tmp/a22/code/FuChuangSai_A22/remote/speech-service
source /root/autodl-tmp/a22/.uv_envs/speech-service/bin/activate
uv sync
```

### 2.2 Download model to fixed path

```bash
python scripts/download_emotion2vec_model.py \
  --repo-id emotion2vec/emotion2vec_plus_base \
  --local-dir /data/zifeng/siyuan/A22/models/emotion2vec_plus_base
```

### 2.3 Update `.env`

```bash
cp .env.example .env
```

Required fields:

- `SER_ENABLED=true`
- `SER_PROVIDER=emotion2vec_plus_base`
- `SER_MODEL=/data/zifeng/siyuan/A22/models/emotion2vec_plus_base`
- `SER_DEVICE=cuda:0` (or your target GPU)

## 3. Vision emotion model (`enet_b2_7`)

### 3.1 Sync dependencies

```bash
cd /root/autodl-tmp/a22/code/FuChuangSai_A22/remote/vision-service
source /root/autodl-tmp/a22/.uv_envs/vision-service/bin/activate
uv sync
```

### 3.2 Prefetch model weights

```bash
python scripts/prefetch_face_emotion_model.py --model-name enet_b2_7 --device cpu
```

### 3.3 Update `.env`

```bash
cp .env.example .env
```

Required fields:

- `FER_ENABLED=true`
- `FER_PROVIDER=hsemotion`
- `FER_MODEL_NAME=enet_b2_7`
- `FER_DEVICE=cpu` (recommended for stability)

## 4. Start services

```bash
# speech-service
cd /root/autodl-tmp/a22/code/FuChuangSai_A22/remote/speech-service
source /root/autodl-tmp/a22/.uv_envs/speech-service/bin/activate
set -a; source .env; set +a
uv run uvicorn app:app --host 127.0.0.1 --port 19100
```

```bash
# vision-service
cd /root/autodl-tmp/a22/code/FuChuangSai_A22/remote/vision-service
source /root/autodl-tmp/a22/.uv_envs/vision-service/bin/activate
set -a; source .env; set +a
uv run uvicorn app:app --host 127.0.0.1 --port 19200
```

## 5. Health checks

```bash
curl http://127.0.0.1:19100/health
curl http://127.0.0.1:19200/health
```

Expected new health fields:

- speech: `ser_enabled`, `ser_provider`, `ser_model`, `ser_device`
- vision: `fer_enabled`, `fer_provider`, `fer_model_name`, `fer_device`

