# RobotMatch / 瓦力家伴：远程服务与树莓派启动指令记录

> 适用仓库：`https://github.com/lfrf/fyfzsylxsRobot`  
> 当前代码路径：`/root/autodl-tmp/a22/code/fyfzsylxsRobot`  
> 当前模型路径：`/root/autodl-tmp/a22/models`  
> 当前环境路径：`/root/autodl-tmp/a22/.uv_envs`  
> 当前环境配置文件：`/root/autodl-tmp/a22/code/fyfzsylxsRobot/scripts/env_robot.sh`  
> 目标链路：`Raspberry Pi raspirobot → SSH tunnel → remote/orchestrator → ASR / Qwen LLM / TTS → RobotChatResponse → Raspberry Pi 播放音频`  
> 当前原则：**robot path 不使用 avatar-service；TTS 单独使用 TTS 环境；orchestrator 只做编排，不直接加载模型。**

---

## 0. 当前远程目录目标结构

你的当前服务器目录应保持如下结构：

```text
/root/autodl-tmp/a22/
├── code/
│   └── fyfzsylxsRobot/     # 新机器人项目
│       ├── remote/
│       ├── scripts/
│       │   └── env_robot.sh
│       ├── shared/
│       ├── tests/
│       └── README.md
│
├── models/
│   ├── Qwen2.5-7B-Instruct
│   ├── Qwen3-ASR-1.7B
│   ├── Qwen2.5-VL-7B-Instruct
│   ├── CosyVoice-300M-Instruct
│   ├── CosyVoice
│   └── ...
│
├── .uv_envs/
│   ├── qwen-server/        # LLM vLLM 环境，可复用旧环境
│   ├── speech-service/     # ASR 环境，可复用旧环境
│   ├── tts-service/        # 新增：TTS 单独环境，不再用 avatar 环境
│   └── orchestrator/       # 轻量编排环境
│
├── tmp/
└── logs/
```

如果你的实际路径不是 `/root/autodl-tmp/a22`，只需要修改 `scripts/env_robot.sh` 里的 `ROBOT_ROOT`。

---

## 1. 总体运行关系

最终服务关系如下：

```text
Raspberry Pi
  raspirobot live_audio_loop
        ↓ SSH tunnel, local 29000
Remote orchestrator :19000
        ↓ ASRClient
Remote ASR service :19100
        ↓ LLMClient
Remote qwen-server :8000
        ↓ TTSClient
Remote TTS service :19200
        ↓ audio proxy
Remote orchestrator /v1/robot/media/tts/...
        ↓ SSH tunnel
Raspberry Pi audio player
```

端口建议：

| 服务 | 端口 | 环境 | 说明 |
|---|---:|---|---|
| qwen-server | 8000 | `.uv_envs/qwen-server` | Qwen2.5-7B-Instruct，OpenAI-compatible API |
| ASR service | 19100 | `.uv_envs/speech-service` | Qwen3-ASR，提供 `/asr/transcribe` |
| TTS service | 19200 | `.uv_envs/tts-service` | CosyVoice，提供 `/tts/synthesize`，不使用 avatar 环境 |
| orchestrator | 19000 | `.uv_envs/orchestrator` | `/v1/robot/chat_turn` 统一入口 |
| Pi tunnel | 29000 | 树莓派本地 | 转发到远程 orchestrator 19000 |

---

## 2. 远程公共环境配置：`scripts/env_robot.sh`

你的 `env_robot.sh` 当前放在：

```text
/root/autodl-tmp/a22/code/fyfzsylxsRobot/scripts/env_robot.sh
```

后续所有命令建议统一使用：

```bash
source /root/autodl-tmp/a22/code/fyfzsylxsRobot/scripts/env_robot.sh
```

为了兼容旧命令，也建议创建一个软链接：

```bash
ln -sf /root/autodl-tmp/a22/code/fyfzsylxsRobot/scripts/env_robot.sh \
  /root/autodl-tmp/a22/env_robot.sh
```

这样下面两种写法都能用：

```bash
source /root/autodl-tmp/a22/code/fyfzsylxsRobot/scripts/env_robot.sh
source /root/autodl-tmp/a22/env_robot.sh
```

### 2.1 创建或覆盖 `scripts/env_robot.sh`

在远程服务器执行：

```bash
mkdir -p /root/autodl-tmp/a22/code/fyfzsylxsRobot/scripts

cat > /root/autodl-tmp/a22/code/fyfzsylxsRobot/scripts/env_robot.sh <<'EOF_ENV'
# ===== RobotMatch common paths =====
export ROBOT_ROOT=${ROBOT_ROOT:-/root/autodl-tmp/a22}
export A22_ROOT=$ROBOT_ROOT
export A22_CODE=${A22_CODE:-$ROBOT_ROOT/code/fyfzsylxsRobot}
export A22_MODEL_ROOT=${A22_MODEL_ROOT:-$ROBOT_ROOT/models}
export A22_ENV_ROOT=${A22_ENV_ROOT:-$ROBOT_ROOT/.uv_envs}
export A22_TMP_ROOT=${A22_TMP_ROOT:-$ROBOT_ROOT/tmp}
export A22_LOG_ROOT=${A22_LOG_ROOT:-$ROBOT_ROOT/logs}

mkdir -p "$A22_ENV_ROOT" "$A22_TMP_ROOT" "$A22_LOG_ROOT"

# ===== Qwen LLM =====
export QWEN_CUDA_VISIBLE_DEVICES=${QWEN_CUDA_VISIBLE_DEVICES:-0}
export QWEN_MODEL_PATH=${QWEN_MODEL_PATH:-$A22_MODEL_ROOT/Qwen2.5-7B-Instruct}
export QWEN_MODEL_NAME=${QWEN_MODEL_NAME:-Qwen2.5-7B-Instruct}
export QWEN_GPU_MEMORY_UTILIZATION=${QWEN_GPU_MEMORY_UTILIZATION:-0.28}
export QWEN_MAX_MODEL_LEN=${QWEN_MAX_MODEL_LEN:-4096}
export QWEN_MAX_NUM_SEQS=${QWEN_MAX_NUM_SEQS:-2}

# ===== ASR =====
export ASR_PROVIDER=${ASR_PROVIDER:-qwen3_asr}
export ASR_MODEL=${ASR_MODEL:-$A22_MODEL_ROOT/Qwen3-ASR-1.7B}
export ASR_DEVICE=${ASR_DEVICE:-cuda:0}
export ASR_LANGUAGE=${ASR_LANGUAGE:-Chinese}
export ASR_WARMUP_ENABLED=${ASR_WARMUP_ENABLED:-true}

# ===== TTS: standalone robot TTS, not avatar-service =====
# 注意：代码读取的是 TTS_REPO_PATH，不是 TTS_CODE_ROOT。
export TTS_PROVIDER=${TTS_PROVIDER:-cosyvoice}
export TTS_MODEL=${TTS_MODEL:-$A22_MODEL_ROOT/CosyVoice-300M-Instruct}
export TTS_REPO_PATH=${TTS_REPO_PATH:-$A22_MODEL_ROOT/CosyVoice}
export TTS_CODE_ROOT=${TTS_CODE_ROOT:-$TTS_REPO_PATH}
export TTS_MODE=${TTS_MODE:-cosyvoice_300m_instruct}
export TTS_DEVICE=${TTS_DEVICE:-cuda:0}
export TTS_SAMPLE_RATE=${TTS_SAMPLE_RATE:-22050}
export TTS_WARMUP_ENABLED=${TTS_WARMUP_ENABLED:-true}
export TTS_ALLOW_MOCK_FALLBACK=${TTS_ALLOW_MOCK_FALLBACK:-true}

# speech-service storage root. TTS 音频会存到 TMP_DIR 下。
export TMP_DIR=${TMP_DIR:-$A22_TMP_ROOT/speech}
mkdir -p "$TMP_DIR"

# ===== Service URLs =====
export SPEECH_SERVICE_BASE=${SPEECH_SERVICE_BASE:-http://127.0.0.1:19100}
export TTS_SERVICE_BASE=${TTS_SERVICE_BASE:-http://127.0.0.1:19200}
export LLM_PROVIDER=${LLM_PROVIDER:-qwen}
export LLM_API_BASE=${LLM_API_BASE:-http://127.0.0.1:8000/v1}
export LLM_MODEL=${LLM_MODEL:-Qwen2.5-7B-Instruct}
export LLM_API_KEY=${LLM_API_KEY:-EMPTY}

# ===== Robot path switches =====
export ROBOT_CHAT_USE_MOCK_ASR=${ROBOT_CHAT_USE_MOCK_ASR:-false}
export ROBOT_CHAT_USE_MOCK_LLM=${ROBOT_CHAT_USE_MOCK_LLM:-false}
export ROBOT_CHAT_USE_MOCK_TTS=${ROBOT_CHAT_USE_MOCK_TTS:-false}

# ===== Logging =====
export ROBOT_LOG_LEVEL=${ROBOT_LOG_LEVEL:-INFO}
export ROBOT_DEBUG_TRACE=${ROBOT_DEBUG_TRACE:-true}
export ROBOT_LOG_JSON=${ROBOT_LOG_JSON:-false}

# ===== Python path helpers =====
export PYTHONPATH="$A22_CODE/shared:$A22_CODE/remote/orchestrator:$A22_CODE/remote/speech-service:$TTS_REPO_PATH:${PYTHONPATH:-}"
EOF_ENV

ln -sf /root/autodl-tmp/a22/code/fyfzsylxsRobot/scripts/env_robot.sh \
  /root/autodl-tmp/a22/env_robot.sh
```

加载：

```bash
source /root/autodl-tmp/a22/code/fyfzsylxsRobot/scripts/env_robot.sh
```

检查模型目录：

```bash
ls -lh "$QWEN_MODEL_PATH"
ls -lh "$ASR_MODEL"
ls -lh "$TTS_MODEL"
ls -lh "$TTS_REPO_PATH"
```

---

## 3. 拉取新机器人项目代码

```bash
source /root/autodl-tmp/a22/code/fyfzsylxsRobot/scripts/env_robot.sh
mkdir -p "$ROBOT_ROOT/code"
cd "$ROBOT_ROOT/code"

if [ ! -d fyfzsylxsRobot ]; then
  git clone https://github.com/lfrf/fyfzsylxsRobot.git
fi

cd fyfzsylxsRobot
git pull
```

---

## 4. 准备远程环境

### 4.1 Qwen 环境

优先复用旧环境：

```bash
source /root/autodl-tmp/a22/code/fyfzsylxsRobot/scripts/env_robot.sh
source "$A22_ENV_ROOT/qwen-server/bin/activate"
python - <<'PY'
import sys
print(sys.executable)
import vllm
print('vllm ok')
PY
```

如果不存在，再创建：

```bash
source /root/autodl-tmp/a22/code/fyfzsylxsRobot/scripts/env_robot.sh
uv venv "$A22_ENV_ROOT/qwen-server" --python 3.11
source "$A22_ENV_ROOT/qwen-server/bin/activate"
uv pip install -U pip
uv pip install vllm
```

> Qwen 环境最重，优先复用，除非旧环境完全不可用。

---

### 4.2 ASR 环境：`speech-service`

ASR 仍使用 `remote/speech-service` 代码，但使用 `speech-service` 环境，端口 `19100`。

优先复用旧 ASR / speech 环境：

```bash
source /root/autodl-tmp/a22/code/fyfzsylxsRobot/scripts/env_robot.sh
source "$A22_ENV_ROOT/speech-service/bin/activate"
cd "$A22_CODE/remote/speech-service"
python - <<'PY'
import sys
print(sys.executable)
import fastapi, uvicorn
from app import app
print('speech-service ASR app import ok')
PY
```

如果不存在，再创建：

```bash
source /root/autodl-tmp/a22/code/fyfzsylxsRobot/scripts/env_robot.sh
uv venv "$A22_ENV_ROOT/speech-service" --python 3.11
source "$A22_ENV_ROOT/speech-service/bin/activate"
uv pip install -U pip
cd "$A22_CODE/remote/speech-service"

if [ -f requirements.txt ]; then
  uv pip install -r requirements.txt
else
  uv pip install fastapi uvicorn pydantic httpx numpy soundfile librosa
fi
```

---

### 4.3 TTS 环境：`tts-service`，不要再用 avatar 环境

TTS 独立环境的目标：

```text
remote/speech-service/routes/tts.py
remote/speech-service/services/tts_service.py
CosyVoice model/code
```

不使用：

```text
remote/avatar-service
avatar-service env
viseme / lip_sync / video rendering
```

创建 TTS 环境：

```bash
source /root/autodl-tmp/a22/code/fyfzsylxsRobot/scripts/env_robot.sh
uv venv "$A22_ENV_ROOT/tts-service" --python 3.11
source "$A22_ENV_ROOT/tts-service/bin/activate"
uv pip install -U pip

# speech-service 的 Web API 依赖
cd "$A22_CODE/remote/speech-service"
if [ -f requirements.txt ]; then
  uv pip install -r requirements.txt
else
  uv pip install fastapi uvicorn pydantic httpx numpy soundfile librosa
fi

# CosyVoice 代码依赖
if [ -f "$TTS_REPO_PATH/requirements.txt" ]; then
  uv pip install -r "$TTS_REPO_PATH/requirements.txt"
fi

# 如果 CosyVoice 是可编辑包，尝试安装为 editable
if [ -f "$TTS_REPO_PATH/setup.py" ] || [ -f "$TTS_REPO_PATH/pyproject.toml" ]; then
  uv pip install -e "$TTS_REPO_PATH"
fi

python - <<'PY'
import sys
print(sys.executable)
import fastapi, uvicorn
print('fastapi/uvicorn ok')
PY
```

> 注意：当前 `remote/speech-service/app.py` 可能会同时 include ASR/TTS router，并在 startup 时 warmup ASR 与 TTS。若 TTS 环境里没有 ASR 依赖，启动 TTS 单独服务时必须设置 `ASR_WARMUP_ENABLED=false`、`SER_WARMUP_ENABLED=false`。

---

### 4.4 Orchestrator 环境

orchestrator 是轻量编排环境。可以复用旧环境，不行就新建。

```bash
source /root/autodl-tmp/a22/code/fyfzsylxsRobot/scripts/env_robot.sh

if [ ! -d "$A22_ENV_ROOT/orchestrator" ]; then
  uv venv "$A22_ENV_ROOT/orchestrator" --python 3.11
fi

source "$A22_ENV_ROOT/orchestrator/bin/activate"
uv pip install -U pip
cd "$A22_CODE/remote/orchestrator"

if [ -f requirements.txt ]; then
  uv pip install -r requirements.txt
else
  uv pip install fastapi uvicorn pydantic httpx
fi

cd "$A22_CODE"
python - <<'PY'
import sys
print(sys.executable)
from app import app
from clients.asr_client import ASRClient
from clients.llm_client import LLMClient
from clients.tts_client import TTSClient
print('orchestrator import ok')
PY
```

---

## 5. 启动远程服务

建议打开四个远程终端窗口，分别前台启动：`qwen`、`asr`、`tts`、`orchestrator`。
前台启动的好处是日志会直接打印在当前终端，便于定位 ASR / LLM / TTS 哪一步失败。

### 5.0 清理旧端口进程（可选）

```bash
pkill -f "vllm.entrypoints.openai.api_server.*--port 8000" || true
pkill -f "uvicorn app:app.*--port 19100" || true
pkill -f "uvicorn app:app.*--port 19200" || true
pkill -f "uvicorn app:app.*--port 19000" || true
```

### 5.1 终端 1：启动 Qwen LLM server

```bash
set -euo pipefail
source /root/autodl-tmp/a22/code/fyfzsylxsRobot/scripts/env_robot.sh
source "$A22_ENV_ROOT/qwen-server/bin/activate"
cd "$A22_CODE/remote/qwen-server"
export CUDA_VISIBLE_DEVICES="$QWEN_CUDA_VISIBLE_DEVICES"
python -m vllm.entrypoints.openai.api_server \
  --host 127.0.0.1 \
  --port 8000 \
  --model "$QWEN_MODEL_PATH" \
  --served-model-name "$QWEN_MODEL_NAME" \
  --dtype auto \
  --gpu-memory-utilization "$QWEN_GPU_MEMORY_UTILIZATION" \
  --max-model-len "$QWEN_MAX_MODEL_LEN" \
  --max-num-seqs "$QWEN_MAX_NUM_SEQS" \
  --trust-remote-code
```

检查：

```bash
curl http://127.0.0.1:8000/v1/models
```

---

### 5.2 终端 2：启动 ASR service，端口 19100

```bash
cd /root/autodl-tmp/a22/code/fyfzsylxsRobot

pkill -f "uvicorn app:app.*--port 19100" || true

set -euo pipefail
source /root/autodl-tmp/a22/code/fyfzsylxsRobot/scripts/env_robot.sh
source "$A22_ENV_ROOT/speech-service/bin/activate"

cd "$A22_CODE/remote/speech-service"

export ASR_PROVIDER=qwen3_asr
export ASR_MODEL="$A22_MODEL_ROOT/Qwen3-ASR-1.7B"
export ASR_DEVICE=cuda:0
export ASR_WARMUP_ENABLED=true

export TTS_PROVIDER=mock
export TTS_WARMUP_ENABLED=false
export TTS_DEVICE=cpu

export TMP_DIR="$A22_TMP_ROOT/speech_asr"
mkdir -p "$TMP_DIR"

export PYTHONPATH="$A22_CODE/shared:$A22_CODE/remote/speech-service:${PYTHONPATH:-}"
export ROBOT_LOG_LEVEL=INFO
export ROBOT_DEBUG_TRACE=true

python -c "import routes.asr, routes.tts; print('speech-service route imports ok')"

python -m uvicorn app:app --host 127.0.0.1 --port 19100 --log-level debug
```

检查：

```bash
curl http://127.0.0.1:19100/health
```

---

### 5.3 终端 3：启动 TTS service，端口 19200，独立 TTS 环境

```bash
set -euo pipefail
source /root/autodl-tmp/a22/code/fyfzsylxsRobot/scripts/env_robot.sh
source "$A22_ENV_ROOT/tts-service/bin/activate"
cd "$A22_CODE/remote/speech-service"

# TTS 独立环境：不使用 avatar-service
export TTS_PROVIDER=cosyvoice
export TTS_MODEL="$A22_MODEL_ROOT/CosyVoice-300M-Instruct"
export TTS_REPO_PATH="$A22_MODEL_ROOT/CosyVoice"
export TTS_CODE_ROOT="$TTS_REPO_PATH"
export TTS_MODE=cosyvoice_300m_instruct
export TTS_DEVICE=cuda:0
export TTS_WARMUP_ENABLED=false
export TTS_ALLOW_MOCK_FALLBACK=true

# 关键：TTS-only 服务不 warmup ASR / SER
export ASR_WARMUP_ENABLED=false
export SER_WARMUP_ENABLED=false
export ASR_PROVIDER=qwen3_asr
export ASR_DEVICE=cpu

export TMP_DIR="$A22_TMP_ROOT/speech_tts"
mkdir -p "$TMP_DIR"

export PYTHONPATH="$A22_CODE/shared:$A22_CODE/remote/speech-service:$TTS_REPO_PATH:$TTS_REPO_PATH/third_party/Matcha-TTS:${PYTHONPATH:-}"
export ROBOT_LOG_LEVEL=INFO
export ROBOT_DEBUG_TRACE=true

python -c "import routes.asr, routes.tts; print('speech-service route imports ok')"

python -m uvicorn app:app --host 127.0.0.1 --port 19200
```

检查：

```bash
curl http://127.0.0.1:19200/health
```

如果 TTS 服务启动时报 ASR 相关错误，说明当前 `speech-service/app.py` 还不支持 TTS-only 启动。需要让 Codex 增加：

```text
SPEECH_ENABLE_ASR=false
SPEECH_ENABLE_TTS=true
```

并让 `app.py` 根据开关决定是否 warmup ASR/TTS。

---

### 5.4 终端 4：启动 orchestrator，端口 19000

```bash
set -euo pipefail
source /root/autodl-tmp/a22/code/fyfzsylxsRobot/scripts/env_robot.sh
source "$A22_ENV_ROOT/orchestrator/bin/activate"
cd "$A22_CODE"

export SPEECH_SERVICE_BASE=http://127.0.0.1:19100
export TTS_SERVICE_BASE=http://127.0.0.1:19200

export LLM_PROVIDER=qwen
export LLM_API_BASE=http://127.0.0.1:8000/v1
export LLM_MODEL=Qwen2.5-7B-Instruct
export LLM_API_KEY=EMPTY

export ROBOT_CHAT_USE_MOCK_ASR=false
export ROBOT_CHAT_USE_MOCK_LLM=false
export ROBOT_CHAT_USE_MOCK_TTS=false

export ROBOT_LOG_LEVEL=INFO
export ROBOT_DEBUG_TRACE=true
export PYTHONPATH="$A22_CODE/shared:$A22_CODE/remote/orchestrator:${PYTHONPATH:-}"

python -m uvicorn app:app \
  --app-dir remote/orchestrator \
  --host 127.0.0.1 \
  --port 19000
```

检查：

```bash
curl http://127.0.0.1:19000/health
```

---

## 6. 远程服务状态检查

```bash
curl http://127.0.0.1:8000/v1/models
curl http://127.0.0.1:19100/health
curl http://127.0.0.1:19200/health
curl http://127.0.0.1:19000/health
```

查看日志：

四个服务都以前台方式运行，日志会直接显示在对应终端窗口中。

杀掉服务：

```bash
pkill -f "vllm.entrypoints.openai.api_server.*--port 8000" || true
pkill -f "uvicorn app:app.*--port 19100" || true
pkill -f "uvicorn app:app.*--port 19200" || true
pkill -f "uvicorn app:app.*--port 19000" || true
```

---

## 7. 远程本机测试 robot endpoint

### 7.1 测试模式切换：绕过 ASR，检查 TTS

```bash
curl -X POST http://127.0.0.1:19000/v1/robot/chat_turn \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "demo-session-001",
    "turn_id": "turn-0001",
    "mode": "elderly",
    "input": {
      "type": "audio_base64",
      "audio_base64": "",
      "audio_format": "wav",
      "sample_rate": 16000,
      "channels": 1,
      "text_hint": "切换为老年模式"
    }
  }'
```

你应该看到：

```text
mode_changed=true
active_rag_namespace=elderly_care
tts.audio_url=/v1/robot/media/tts/...
debug.sources.tts 不是 mock / fallback 时表示真实 TTS 已启用
```

### 7.2 测试 LLM：仍绕过 ASR

```bash
curl -X POST http://127.0.0.1:19000/v1/robot/chat_turn \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "demo-session-001",
    "turn_id": "turn-0002",
    "mode": "elderly",
    "input": {
      "type": "audio_base64",
      "audio_base64": "",
      "audio_format": "wav",
      "sample_rate": 16000,
      "channels": 1,
      "text_hint": "我今天有点累"
    }
  }'
```

检查 debug：

```text
debug.sources.llm=qwen_vllm
debug.fallback.llm=false
```

### 7.3 测试 TTS 音频链接是否可下载

把 7.1 或 7.2 返回里的 `tts.audio_url` 复制出来，例如：

```text
/v1/robot/media/tts/demo-session-001/turn-0002.wav
```

然后测试：

```bash
curl -I http://127.0.0.1:19000/v1/robot/media/tts/demo-session-001/turn-0002.wav
```

如果返回 `200`，说明 orchestrator 的 TTS proxy 能拿到音频。

如果返回 `404`，重点检查：

```text
TTS service 终端日志
orchestrator 终端日志
```

---

## 8. 树莓派环境与启动

### 8.1 树莓派创建本地 venv

```bash
cd /home/pi/Desktop/code/fyfzsylxsRobot
git pull

sudo apt-get update
sudo apt-get install -y alsa-utils python3-venv

bash scripts/setup_raspi_venv.sh
source .venv/bin/activate
bash scripts/check_raspi_env.sh
```

如果你的 venv 在 `raspirobot/.venv`，改用：

```bash
source raspirobot/.venv/bin/activate
```

---

### 8.2 树莓派建立 SSH 隧道

```bash
ssh -N \
  -o ExitOnForwardFailure=yes \
  -o ServerAliveInterval=30 \
  -o ServerAliveCountMax=3 \
  -L 127.0.0.1:29000:127.0.0.1:19000 \
  -p 57547 root@connect.bjb1.seetacloud.com
```

检查：

```bash
curl http://127.0.0.1:29000/health
```

---

### 8.3 树莓派运行真实麦克风持续监听

```bash
cd /home/pi/Desktop/code/fyfzsylxsRobot
source .venv/bin/activate

mkdir -p /home/pi/Desktop/code/fyfzsylxsRobot/tmp/wav

export ROBOT_REMOTE_BASE_URL=http://127.0.0.1:29000
export ROBOT_AUDIO_WORK_DIR=/home/pi/Desktop/code/fyfzsylxsRobot/tmp/wav

export ROBOT_AUDIO_CAPTURE_PROVIDER=local_command
export ROBOT_AUDIO_OUTPUT_PROVIDER=local_command
export ROBOT_AUDIO_CAPTURE_COMMAND=arecord
export ROBOT_AUDIO_PLAYBACK_COMMAND=aplay
export ROBOT_AUDIO_CAPTURE_DEVICE=plughw:3,0
export ROBOT_AUDIO_PLAYBACK_DEVICE=plughw:3,0
export ROBOT_AUDIO_SAMPLE_RATE=16000
export ROBOT_AUDIO_CHANNELS=2

export ROBOT_LOG_LEVEL=INFO
export ROBOT_DEBUG_TRACE=true

python -m raspirobot.scripts.live_audio_loop
```

正常日志应看到：

```text
listening_started
speech_started
speech_ended
utterance_saved
payload_built
remote_request_started
remote_request_succeeded
remote_response_received
playback_started / playback_done
```

---

## 9. 树莓派端快速测试命令

### 9.1 检查远程 tunnel

```bash
curl http://127.0.0.1:29000/health
```

### 9.2 直接用现有 wav 走远程链路

如果你有一个 wav 文件：

```bash
python -m raspirobot.scripts.audio_tunnel_smoke --wav /tmp/robot_test.wav
```

如果要尝试播放：

```bash
python -m raspirobot.scripts.audio_tunnel_smoke --wav /tmp/robot_test.wav --play
```

### 9.3 真实麦克风录音检查

```bash
arecord -l
arecord -D plughw:3,0 -f S16_LE -r 16000 -c 2 -d 3 /tmp/test.wav
aplay /tmp/test.wav
```

---

## 10. 如何判断真实 ASR / LLM / TTS 已经启用

看 orchestrator 日志或 `RobotChatResponse.debug`：

```text
ASR 真实：debug.sources.asr 不是 mock / fallback / text_hint
LLM 真实：debug.sources.llm=qwen_vllm 且 debug.fallback.llm=false
TTS 真实：debug.sources.tts 不是 mock，tts.audio_url 为 /v1/robot/media/tts/...wav
```

典型成功字段：

```json
{
  "debug": {
    "sources": {
      "asr": "speech_service",
      "llm": "qwen_vllm",
      "tts": "speech_service_tts"
    },
    "fallback": {
      "asr": false,
      "llm": false,
      "tts": false
    }
  }
}
```

---

## 11. 常见问题

### 11.1 TTS 仍然使用 avatar 环境怎么办？

不要再启动 `remote/avatar-service`。  
TTS 应从 `remote/speech-service/routes/tts.py` 和 `remote/speech-service/services/tts_service.py` 提供。

如果历史 TTS 代码还在 avatar-service 中，建议下一步只抽取“文本转 wav”的部分进入 `speech-service/services/tts_service.py`，不要引入：

```text
avatar_action
viseme
lip_sync
video_url
SoulX-FlashHead
UE/A2F rendering
```

### 11.2 TTS service 启动时 ASR 报错

说明当前 `speech-service/app.py` 启动时强制 warmup ASR。  
短期先设置：

```bash
export ASR_WARMUP_ENABLED=false
export SER_WARMUP_ENABLED=false
```

如果仍失败，需要代码改造：

```text
SPEECH_ENABLE_ASR=false
SPEECH_ENABLE_TTS=true
```

并在 `app.py` 里根据开关控制 warmup。

### 11.3 qwen-server 不通

```bash
curl http://127.0.0.1:8000/v1/models
```

若不通，检查 Qwen LLM server 对应终端日志：

```text
终端 1：Qwen LLM server
```

### 11.4 ASR 不通

```bash
curl http://127.0.0.1:19100/health
```

看 orchestrator 日志里的：

```text
asr_result source=fallback...
```

### 11.5 TTS 不通

```bash
curl http://127.0.0.1:19200/health
```

看 orchestrator 日志里的：

```text
tts_result source=fallback...
audio_url=mock://...
```

### 11.6 Pi 录不到声音

```bash
arecord -l
arecord -D plughw:3,0 -f S16_LE -r 16000 -c 2 -d 3 /tmp/test.wav
aplay /tmp/test.wav
```

如果没有声音，换设备号或声道。

---

## 12. 建议保存为项目文档

建议将本文保存为：

```text
scripts/ROBOTMATCH_REMOTE_RASPI_STARTUP_GUIDE.md
```

也可以另存为：

```text
scripts/ROBOT_FULL_STARTUP_WITH_TTS_ENV.md
```

本文用于“ASR / LLM / 单独 TTS 环境”的完整运行。
