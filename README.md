# RobotMatch / 瓦力家伴

RobotMatch 是一个从旧数字人情感陪伴项目迁移而来的 Raspberry Pi 桌面陪伴机器人项目，目标是让远端 LLM 情感陪伴能力驱动一个真实的桌面机器人身体。

## 当前架构

V1 主运行链路：

```text
Robot peripherals
camera / microphone / speaker / OLED / servos
        ↓
Raspberry Pi 5 raspirobot
audio listener / VAD / state machine / remote client / hardware interfaces
        ↓
SSH tunnel / HTTP JSON
remote/orchestrator
ASR client / Qwen LLM client / TTS client / mode logic / RAG routing stub / robot action
        ↓
remote/speech-service + remote/qwen-server
ASR + robot TTS / Qwen2.5-7B-Instruct OpenAI-compatible API
```

笔记本电脑只用于开发、SSH 登录、日志查看和调试，不属于主运行链路。

## V1 当前状态

已经具备：

- `raspirobot/` Raspberry Pi 侧运行骨架；
- mock-only 硬件接口：唤醒词、录音、播放、人脸跟踪、视觉上下文、OLED 眼睛、头部动作；
- 统一机器人接口：`POST /v1/robot/chat_turn`；
- JSON + `audio_base64` 请求格式，不使用 multipart 作为 V1 主路径；
- session-based 模式切换；
- 模式到 RAG namespace 的路由 stub；
- de-avatarized robot TTS client；
- remote/speech-service ASR/TTS 路由；
- remote/qwen-server OpenAI-compatible LLM 接入；
- robot action 生成；
- 最小 smoke tests。

Pi 侧现在已有可运行的基础语音循环：

```text
continuous microphone listening
→ EnergyVAD 检测语音
→ 静音超时后保存 wav
→ wav 转 audio_base64 JSON
→ RemoteClient 调用 /v1/robot/chat_turn
→ 接收 RobotChatResponse
→ 下载/播放 tts.audio_url
→ dispatch robot_action
→ 回到 LISTENING
```

OLED、舵机、摄像头、人脸跟踪和唤醒词仍是接口/mock。RAG 仍是 namespace 路由 stub。

## 目录结构

```text
fyfzsylxsRobot/
├── raspirobot/
│   ├── app.py
│   ├── main.py
│   ├── config.py
│   ├── core/
│   ├── remote/
│   ├── audio/
│   ├── vision/
│   ├── hardware/
│   ├── actions/
│   ├── session/
│   ├── utils/
│   └── scripts/
├── remote/
│   ├── orchestrator/
│   │   ├── app.py
│   │   ├── clients/
│   │   │   ├── asr_client.py
│   │   │   ├── llm_client.py
│   │   │   └── tts_client.py
│   │   ├── routes/
│   │   │   ├── robot_chat.py
│   │   │   └── robot_media.py
│   │   └── services/
│   │       ├── robot_chat_service.py
│   │       ├── mode_manager.py
│   │       ├── mode_policy.py
│   │       ├── rag_router.py
│   │       └── robot_action_service.py
│   ├── qwen-server/
│   └── speech-service/
│       ├── routes/
│       │   ├── asr.py
│       │   └── tts.py
│       └── services/
│           ├── asr_service.py
│           └── tts_service.py
├── shared/
│   ├── schemas.py
│   └── contracts/
│       └── schemas.py
└── tests/
```

## Robot Chat 接口

Endpoint:

```text
POST /v1/robot/chat_turn
Content-Type: application/json
```

最小请求示例：

```json
{
  "session_id": "demo-session-001",
  "turn_id": "turn-0001",
  "mode": "care",
  "input": {
    "type": "audio_base64",
    "audio_base64": "UklGRiQAAABXQVZFZm10IBAAAAABAAEA",
    "audio_format": "wav",
    "sample_rate": 16000,
    "channels": 1,
    "text_hint": "切换为关怀模式"
  }
}
```

测试里 `text_hint` 可以绕过 ASR。正常机器人路径会由 `remote/orchestrator/clients/asr_client.py` 调用 `remote/speech-service` 的 ASR 路由。

响应遵循 `RobotChatResponse`，包含：

- `mode`
- `mode_switch`
- `mode_changed`
- `active_rag_namespace`
- `asr_text`
- `reply_text`
- `emotion`
- `tts`
- `robot_action`

机器人路径不会返回 `avatar_output`、`avatar_action`、`viseme`、`lip_sync` 或视频 URL。

## 模式切换

当前支持四种产品模式。内部 `mode_id` 统一使用新 ID：

| mode_id | 中文名 | rag_namespace | speech_style |
| --- | --- | --- | --- |
| `care` | 关怀模式 | `care` | `care_gentle` |
| `accompany` | 陪伴模式 | `general` | `natural_warm` |
| `learning` | 学习模式 | `learning` | `learning_focused` |
| `game` | 游戏模式 | `game` | `game_playful` |

当前第一版只支持显式切换命令：

```text
关怀：切换为关怀模式 / 进入关怀模式
陪伴：切换为陪伴模式 / 进入陪伴模式
学习：切换为学习模式 / 进入学习模式
游戏：切换为游戏模式 / 进入游戏模式
```

隐性切换后续再做。比如“我有点累”“帮我复习”“玩个游戏”“陪我聊聊天”暂时不会自动切换模式。

旧 ID 仅作为兼容 alias 接收，系统内部和响应都会返回新 ID：

```text
elderly -> care
normal -> accompany
student -> learning
child -> game
```

`game` 模式当前只提供显式切换和游戏风格 LLM 回复；完整猜谜语 / 词语接龙状态机后续实现。

检测到模式切换后，`remote/orchestrator` 会：

1. 更新内存 session mode：`session_id -> mode`；
2. 返回 `mode_changed=true`；
3. 返回 `active_rag_namespace`；
4. 返回简短确认回复；
5. 返回适合该模式的 `robot_action`；
6. 不生成长篇普通聊天回复。

## 运行 remote/orchestrator

进入 orchestrator：

```bash
cd fyfzsylxsRobot/remote/orchestrator
```

安装依赖后启动：

```bash
uvicorn app:app --host 127.0.0.1 --port 19000
```

也可以使用已有 `uv` 环境：

```bash
uv run uvicorn app:app --host 127.0.0.1 --port 19000
```

检查 health：

```bash
curl http://127.0.0.1:19000/health
```

检查机器人接口：

```bash
curl -X POST http://127.0.0.1:19000/v1/robot/chat_turn \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "demo-session-001",
    "turn_id": "turn-0001",
    "mode": "care",
    "input": {
      "type": "audio_base64",
      "audio_base64": "UklGRiQAAABXQVZFZm10IBAAAAABAAEA",
      "audio_format": "wav",
      "sample_rate": 16000,
      "channels": 1,
      "text_hint": "切换为游戏模式"
    }
  }'
```

真实 ASR/LLM/TTS 链路启动细节见：

```text
scripts/ROBOT_CHAIN_STARTUP.md
```

orchestrator 的真实链路环境变量示例：

```bash
export SPEECH_SERVICE_BASE=http://127.0.0.1:19100
export TTS_SERVICE_BASE=http://127.0.0.1:19200
export LLM_PROVIDER=qwen
export LLM_API_BASE=http://127.0.0.1:8000/v1
export LLM_MODEL=Qwen2.5-7B-Instruct
export LLM_API_KEY=EMPTY
export ROBOT_CHAT_USE_MOCK_ASR=false
export ROBOT_CHAT_USE_MOCK_LLM=false
export ROBOT_CHAT_USE_MOCK_TTS=false
```

## 检查 raspirobot

创建树莓派本地 venv：

```bash
cd fyfzsylxsRobot
bash scripts/setup_raspi_venv.sh
source .venv/bin/activate
bash scripts/check_raspi_env.sh
```

Pi 侧配置通过环境变量控制：

```bash
export ROBOT_REMOTE_BASE_URL=http://127.0.0.1:29000
export ROBOT_CHAT_ENDPOINT=/v1/robot/chat_turn
export ROBOT_REMOTE_TIMEOUT_SECONDS=40
export ROBOT_MODE_DEFAULT=care
export ROBOT_SESSION_ID=demo-session-001
```

音频配置也通过环境变量控制，不在业务逻辑中硬编码设备：

```bash
export ROBOT_AUDIO_CAPTURE_PROVIDER=local_command
export ROBOT_AUDIO_OUTPUT_PROVIDER=local_command
export ROBOT_AUDIO_CAPTURE_COMMAND=arecord
export ROBOT_AUDIO_PLAYBACK_COMMAND=aplay
export ROBOT_AUDIO_CAPTURE_DEVICE=plughw:3,0
export ROBOT_AUDIO_PLAYBACK_DEVICE=plughw:3,0
export ROBOT_AUDIO_SAMPLE_RATE=16000
export ROBOT_AUDIO_CHANNELS=2
export ROBOT_AUDIO_FRAME_MS=30
export ROBOT_VAD_RMS_THRESHOLD=500
export ROBOT_VAD_SPEECH_START_FRAMES=3
export ROBOT_VAD_SILENCE_TIMEOUT_MS=900
export ROBOT_VAD_MAX_UTTERANCE_SECONDS=15
export ROBOT_VAD_PRE_ROLL_MS=300
```

已知 ReSpeaker/USB 麦克风可能需要双声道，若单声道录音没有声音，请保持 `ROBOT_AUDIO_CHANNELS=2`。

最小导入检查：

```bash
cd fyfzsylxsRobot
python3.11 - <<'PY'
from raspirobot.state_machine import RobotStateMachine
from raspirobot.remote_client import RemoteClient, MockRemoteClient
from raspirobot.actions import DefaultRobotActionDispatcher

print(RobotStateMachine())
print(RemoteClient().url)
print(MockRemoteClient())
print(DefaultRobotActionDispatcher.with_mocks())
PY
```

## Raspberry Pi 侧语音循环

### 1. 文件 wav mock 闭环

用于不依赖真实麦克风、不依赖远端服务的本地流程测试：

```bash
cd fyfzsylxsRobot
python3.11 -m raspirobot.scripts.file_audio_mock_loop --wav /tmp/robot_test.wav
```

该脚本会：

```text
FileAudioInputProvider
→ EnergyVAD
→ 保存 utterance wav
→ RobotPayloadBuilder
→ MockRemoteClient
→ MockAudioOutputProvider
→ 回到 LISTENING
```

### 2. SSH 隧道远端接口 smoke

先在远端启动 orchestrator，并在树莓派建立隧道：

```bash
ssh -N \
  -o ExitOnForwardFailure=yes \
  -o ServerAliveInterval=30 \
  -o ServerAliveCountMax=3 \
  -L 127.0.0.1:29000:127.0.0.1:19000 \
  -p 57547 root@connect.bjb1.seetacloud.com
```

确认：

```bash
curl http://127.0.0.1:29000/health
```

发送已有 wav 到远端：

```bash
cd fyfzsylxsRobot
export ROBOT_REMOTE_BASE_URL=http://127.0.0.1:29000
python3.11 -m raspirobot.scripts.audio_tunnel_smoke --wav /tmp/robot_test.wav
```

如果远端返回真实可下载 `tts.audio_url`，可以播放：

```bash
python3.11 -m raspirobot.scripts.audio_tunnel_smoke --wav /tmp/robot_test.wav --play
```

如果 orchestrator 仍在 mock TTS 模式，远端可能返回 `mock://...`，这种 URL 不会被本地播放器播放。真实 TTS 模式下应返回 `/v1/robot/media/tts/...wav`，树莓派会通过 orchestrator 隧道下载。

### 3. 真实麦克风持续监听循环

树莓派上运行：

```bash
cd fyfzsylxsRobot
export ROBOT_REMOTE_BASE_URL=http://127.0.0.1:29000
export ROBOT_AUDIO_CAPTURE_DEVICE=plughw:3,0
export ROBOT_AUDIO_PLAYBACK_DEVICE=plughw:3,0
export ROBOT_AUDIO_SAMPLE_RATE=16000
export ROBOT_AUDIO_CHANNELS=2
python3.11 -m raspirobot.scripts.live_audio_loop
```

该入口使用 `arecord -t raw` 持续读取音频帧，通过 `EnergyVAD` 切出一句话，发送给远端，收到结果后播放返回音频，再回到监听。

## 运行日志与链路诊断

raspirobot 和 remote/orchestrator 共享 `shared/logging_utils.py`，默认输出人类可读终端日志。

建议调试时打开：

```bash
export ROBOT_LOG_LEVEL=INFO
export ROBOT_DEBUG_TRACE=true
```

如果需要 JSON 风格日志：

```bash
export ROBOT_LOG_JSON=true
```

日志不会打印完整 `audio_base64`，只会打印长度和音频元数据，例如：

```text
event=payload_built session_id=demo-session-001 turn_id=turn-0001 mode=care sample_rate=16000 channels=2 audio_base64_len=123456
```

Pi 侧关键日志：

```text
listening_started
speech_started
speech_ended
utterance_saved
payload_built
remote_request_started
remote_request_succeeded
remote_response_received
playback_started / playback_skipped / playback_done
```

远端关键日志：

```text
robot_chat_request_received
asr_request_started
asr_result
mode_switch_detected
llm_request_started
llm_result
tts_request_started
tts_result
robot_chat_response_ready
```

判断是否使用真实服务：

- ASR 真实：`asr_result source=remote_qwen3_asr` 或 speech-service 返回的真实来源，且 `fallback=false`。
- ASR mock：`source=mock_enabled_or_missing_base` 或 `source=fallback_after_error:...`。
- ASR text_hint 绕过：`source=text_hint`，这是测试路径。
- LLM 真实：`llm_result source=qwen_vllm fallback=false`。
- LLM fallback/mock：`source=mock` 或 `source=fallback:qwen_vllm:... fallback=true`。
- TTS 真实：`tts_result audio_url=/v1/robot/media/tts/...wav` 或 speech-service URL，且 `fallback=false`。
- TTS mock：`audio_url=mock://... fallback=true`，Pi 会跳过播放并回到监听。

`RobotChatResponse.debug` 会包含诊断信息：

```json
{
  "trace_id": "...",
  "sources": {
    "asr": "...",
    "llm": "...",
    "tts": "..."
  },
  "latency_ms": {
    "asr": 0,
    "llm": 0,
    "tts": 0,
    "total": 0
  },
  "service_urls": {
    "speech_service": "http://127.0.0.1:19100",
    "tts_service": "http://127.0.0.1:19100",
    "llm_api_base": "http://127.0.0.1:8000/v1"
  },
  "fallback": {
    "asr": false,
    "llm": false,
    "tts": false
  }
}
```

常见问题：

- ASR service 不通：看 `asr_result source=fallback_after_error:...`，检查 `SPEECH_SERVICE_BASE` 和 `curl http://127.0.0.1:19100/health`。
- Qwen server 不通：看 `llm_result source=fallback:qwen_vllm:...`，检查 `LLM_API_BASE` 和 `curl http://127.0.0.1:8000/v1/models`。
- TTS service 不通：看 `tts_result source=fallback:... audio_url=mock://...`，检查 `TTS_SERVICE_BASE`。
- 缺少 `audio_url`：Pi 会输出 `playback_skipped skipped_reason=empty audio_url`。
- `mock://` audio_url：Pi 会输出 `playback_skipped skipped_reason=mock audio_url is not playable`。
- 没有音频设备：先运行 `bash scripts/check_raspi_env.sh`，再检查 `arecord -l` 和 `aplay -l`。

启动 raspirobot skeleton health app：

```bash
cd fyfzsylxsRobot
uvicorn raspirobot.app:app --host 127.0.0.1 --port 18081
```

## 运行测试

```bash
cd fyfzsylxsRobot
python3.11 -m pytest tests/test_robot_skeleton.py tests/test_robot_chat_logic.py
```

如果当前机器没有安装 `pytest` 或 `pydantic`，先按项目环境安装依赖。V1 测试不需要 Raspberry Pi 硬件。

## 当前有意不实现的内容

本轮不实现：

- 真实摄像头采集；
- OLED SPI；
- PCA9685 / 舵机控制；
- 唤醒词引擎；
- 人脸跟踪算法；
- 真实 RAG 检索；
- 数据库 session 存储；
- ROS2；
- avatar-service、lip-sync 或数字人视频输出。

本轮已经实现的是 Linux/Raspberry Pi 兼容的音频输入/输出 provider 基线：

- `LocalCommandAudioInputProvider`：通过可配置命令读取麦克风音频；
- `EnergyVAD`：能量阈值语音检测和静音端点；
- `AudioListenWorker`：保存 utterance wav；
- `LocalCommandAudioOutputProvider`：下载并播放远端音频 URL；
- `RobotPayloadBuilder`：wav 到 base64 JSON；
- `RaspiRobotRuntime`：单线程 turn-based 语音循环。

本轮远端机器人路径新增：

- `ASRClient`：调用 speech-service `/asr/transcribe`；
- `LLMClient`：调用 qwen-server OpenAI-compatible `/chat/completions`；
- `TTSClient`：调用 speech-service `/tts/synthesize`；
- `robot_media`：把 speech-service TTS 音频代理成 `/v1/robot/media/tts/...wav`，方便树莓派只通过 orchestrator 隧道下载。

硬件同事后续需要实现：

- OLED `EyesDriver` 真实驱动；
- 头部运动 `HeadDriver` 真实驱动；
- 摄像头 `CameraProvider`；
- 人脸跟踪 `FaceTrackerProvider`；
- 唤醒词 provider；
- 根据实际麦克风阵列调整默认声道、阈值和设备名。

## 清理状态

旧数字人主链路已经从 active runtime 中移除：

```text
a22_demo/
local/
tmp/avatar_bridge/
tmp/ue_a2f_runtime/
tmp/ready_model/
compose.local.yaml
compose.robot.yaml
old frontend / edge-backend / local robot-runtime startup files
```

`remote/avatar-service/` 暂时保留为 quarantine 状态，因为其中包含 CosyVoice/TTS runtime 代码，后续应先把可复用 TTS 能力抽取到机器人 TTS 服务，再删除 avatar 渲染部分。

以下能力仍保留，因为它们可能属于机器人远端脑：

- `remote/orchestrator/`
- `remote/speech-service/`
- `remote/qwen-server/`
- `remote/vision-service/`
- `shared/`
- `raspirobot/`
