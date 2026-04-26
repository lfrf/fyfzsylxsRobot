# Avatar Service

`avatar-service` 负责两件事：

- 用 CosyVoice 生成回复音频
- 用 EchoMimic v2 基于音频生成数字人视频

当前仓库已经固定了依赖版本。下次换服务器时，不要凭记忆手装新版依赖，直接按本文档创建独立虚拟环境并同步锁定依赖。

## 1. 目录级虚拟环境

不要把所有远端服务共用一个 `.venv`。

推荐结构：

```text
remote/avatar-service/.venv
```

这样做的原因：

- `avatar-service` 的 `torch/CUDA/transformers` 依赖重
- 与 `speech-service`、`orchestrator` 共用环境时更容易冲突
- 迁移到新服务器时更容易单独排查

## 2. 已固定的关键版本

依赖来源：

- [pyproject.toml](D:\a22\FuChuangSai_A22\remote\avatar-service\pyproject.toml)
- [uv.lock](D:\a22\FuChuangSai_A22\remote\avatar-service\uv.lock)

迁移时必须遵守：

- Python 固定用 `3.11`
- 优先用 `uv sync`
- 不要把 `torch`、`torchaudio`、`transformers`、`onnxruntime-gpu` 单独升级
- 不要在已跑通环境上再执行 `pip install -U ...`
- 不要把旧服务器的 `.venv` 直接拷到新服务器

这些是之前最容易炸环境的点。

## 3. 前置目录准备

你需要准备 4 类路径：

1. A22 项目代码目录
2. CosyVoice 模型目录
3. CosyVoice 仓库目录
4. EchoMimic 仓库目录

建议示例：

```text
/root/autodl-tmp/a22/code/FuChuangSai_A22
/data/zifeng/siyuan/A22/models/CosyVoice2-0.5B
/root/autodl-tmp/a22/models/CosyVoice
/root/autodl-tmp/a22/models/EchoMimicV2
```

注意：

- `TTS_MODEL` 是模型权重目录
- `TTS_REPO_PATH` 是 CosyVoice 源码仓库目录
- 这两个路径不是一回事，别混

## 4. 新服务器安装步骤

进入服务目录：

```bash
cd /root/autodl-tmp/a22/code/FuChuangSai_A22/remote/avatar-service
```

创建虚拟环境：

```bash
uv venv --python /usr/bin/python3.11 .venv
source .venv/bin/activate
```

同步固定依赖：

```bash
uv sync
```

如果 `uv sync` 不可用，再退回：

```bash
uv pip install -r requirements.txt
```

但优先级始终是 `uv sync > requirements.txt`。

## 5. 环境变量

参考：

- [.env.example](D:\a22\FuChuangSai_A22\remote\avatar-service\.env.example)
- [config.py](D:\a22\FuChuangSai_A22\remote\avatar-service\config.py)

最低需要确认这些变量：

- `TMP_DIR`
- `ECHOMIMIC_ROOT`
- `ECHOMIMIC_INFER_SCRIPT`
- `ECHOMIMIC_REF_IMAGE_PATH`
- `ECHOMIMIC_POSE_DIR`
- `TTS_MODE`
- `TTS_MODEL`
- `TTS_REPO_PATH`
- `TTS_DEVICE`

## 6. 启动命令

```bash
cd /root/autodl-tmp/a22/code/FuChuangSai_A22/remote/avatar-service
source .venv/bin/activate
set -a
source .env
set +a
uv run uvicorn app:app --host 127.0.0.1 --port 19300
```

## 7. 健康检查

```bash
curl http://127.0.0.1:19300/health
```

如果 TTS 和数字人都正常，再测生成：

```bash
curl -X POST http://127.0.0.1:19300/generate \
  -H "Content-Type: application/json" \
  -d '{"session_id":"demo-test","turn_id":1,"reply_text":"你好","emotion_style":"supportive","avatar_action":{"facial_expression":"gentle_smile","head_motion":"nod"},"turn_time_window":{"stream_id":"demo","start_ms":0,"end_ms":1000}}'
```

## 8. 迁移时必须规避的坑

1. 不要在新服务器上直接 `pip install torch transformers` 自己拼版本。
2. 不要把 `CosyVoice` 仓库路径填到 `TTS_MODEL`。
3. 不要把 `CosyVoice2-0.5B` 模型目录填到 `TTS_REPO_PATH`。
4. 不要漏配 `ECHOMIMIC_ROOT`，否则只会退回音频，出不了视频。
5. 不要把 `infer.py` 和 `infer_acc.py` 混用；当前优先按实际仓库选择，默认建议 `infer_acc.py`。
6. 不要把旧 `.venv` 打包上传到新服务器复用。
7. 新服务器若 CUDA 或驱动变了，优先重建 `.venv`，不要在旧环境上修补。

## 9. 推荐做法

每次迁移只做两件事：

1. 复制代码仓库
2. 重新执行 `uv venv` + `uv sync` + `.env`

不要手动回忆依赖安装顺序。
