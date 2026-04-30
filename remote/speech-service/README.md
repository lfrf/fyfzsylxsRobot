# Speech Service

`speech-service` 负责远端 ASR 转写、机器人 TTS 语音合成和基础语音特征提取。

Robot path uses:

```text
POST /asr/transcribe
POST /tts/synthesize
GET  /tts/audio/{session_id}/{turn_id}.wav
```

This service is not an avatar renderer and must not return viseme, lip-sync or video output.

当前仓库已经把依赖版本锁住。下次换服务器时，直接重建独立环境，不要混装。

## 1. 目录级虚拟环境

推荐结构：

```text
remote/speech-service/.venv
```

不要与 `orchestrator` 或其他远端模型服务共用环境。

## 2. 已固定的关键版本

依赖来源：

- [pyproject.toml](D:\a22\FuChuangSai_A22\remote\speech-service\pyproject.toml)
- [uv.lock](D:\a22\FuChuangSai_A22\remote\speech-service\uv.lock)

迁移时必须遵守：

- Python 固定 `3.11`
- 优先执行 `uv sync`
- 不要手动升级 `torch`、`torchaudio`、`transformers`
- 不要把 `qwen-asr` 单独升到未验证版本
- 不要复用旧服务器打包出来的 `.venv`

## 3. 当前支持的 ASR/TTS 后端

见 [config.py](D:\a22\FuChuangSai_A22\remote\speech-service\config.py) 与 [asr_runtime.py](D:\a22\FuChuangSai_A22\remote\speech-service\services\asr_runtime.py)：

- `ASR_PROVIDER=belle_whisper`
- `ASR_PROVIDER=qwen3_asr`

当前默认 ASR 配置是 `qwen3_asr`。

如果你没有明确切到 `qwen3_asr`，就不要改这个值。

TTS 由 `remote/speech-service/services/tts_service.py` 管理：

- `TTS_PROVIDER=cosyvoice`
- `TTS_MODEL=/root/autodl-tmp/a22/models/CosyVoice-300M-Instruct`
- `TTS_MODE=cosyvoice_300m_instruct`

如果真实 CosyVoice 不可用且 `TTS_ALLOW_MOCK_FALLBACK=true`，服务会返回一个可播放的 mock wav，方便链路不断。

## 4. 新服务器安装步骤

进入目录：

```bash
cd /root/autodl-tmp/a22/code/FuChuangSai_A22/remote/speech-service
```

创建环境：

```bash
uv venv --python /usr/bin/python3.11 .venv
source .venv/bin/activate
```

同步依赖：

```bash
uv sync
```

兜底方式：

```bash
uv pip install -r requirements.txt
```

## 5. 环境变量

参考：

- [.env.example](D:\a22\FuChuangSai_A22\remote\speech-service\.env.example)
- [config.py](D:\a22\FuChuangSai_A22\remote\speech-service\config.py)

最低需要确认：

- `ASR_PROVIDER`
- `ASR_MODEL`
- `ASR_LANGUAGE`
- `ASR_DEVICE`
- `TTS_PROVIDER`
- `TTS_MODEL`
- `TTS_DEVICE`
- `TTS_MODE`
- `TMP_DIR`

## 6. 启动命令

```bash
cd /root/autodl-tmp/a22/code/FuChuangSai_A22/remote/speech-service
source .venv/bin/activate
set -a
source .env
set +a
uv run uvicorn app:app --host 127.0.0.1 --port 19100
```

## 7. 健康检查

```bash
curl http://127.0.0.1:19100/health
```

转写接口：

```bash
curl -X POST http://127.0.0.1:19100/asr/transcribe \
  -H "Content-Type: application/json" \
  -d '{"session_id":"demo-test","turn_id":"turn-0001","text_hint":"你好"}'
```

TTS 接口：

```bash
curl -X POST http://127.0.0.1:19100/tts/synthesize \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "demo-test",
    "turn_id": "turn-0001",
    "text": "你好，我是瓦力家伴。",
    "mode": "care",
    "speech_style": "care_gentle"
  }'
```

## 8. 迁移时必须规避的坑

1. 不要在 `belle_whisper` 和 `qwen3_asr` 之间来回改，但模型路径不一起改。
2. 不要在环境已经跑通后执行 `pip install -U transformers torch`。
3. 不要拿 CPU 环境去照搬 `cuda:0` 配置。
4. 不要把模型下载到临时目录，迁移后路径一变就失效。
5. 新服务器如果 CUDA 栈不同，优先删掉 `.venv` 重建。

## 9. 推荐做法

只保留三类可迁移资产：

- 代码仓库
- 模型目录
- `.env.example`

不要保留旧 `.venv`。
