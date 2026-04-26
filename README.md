# RobotMatch / 瓦力家伴

RobotMatch 是一个从旧数字人情感陪伴项目迁移而来的 Raspberry Pi 桌面陪伴机器人项目，目标是让远端 LLM 情感陪伴能力驱动一个真实的桌面机器人身体。

## 当前架构

V1 主运行链路：

```text
Robot peripherals
camera / microphone / speaker / OLED / servos
        ↓
Raspberry Pi 5 raspirobot
state machine / remote client / mock hardware interfaces
        ↓
SSH tunnel / HTTP JSON
remote/orchestrator
ASR stub / mode logic / RAG routing stub / TTS stub / robot action
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
- de-avatarized TTS stub；
- robot action 生成；
- 最小 smoke tests。

当前仍然是 mock/stub 逻辑层，不包含真实硬件、真实 ASR、真实 TTS、真实 LLM 或完整 RAG。

## 目录结构

```text
fyfzsylxsRobot/
├── raspirobot/
│   ├── app.py
│   ├── config.py
│   ├── state_machine.py
│   ├── remote_client.py
│   ├── audio/
│   ├── vision/
│   ├── hardware/
│   └── actions/
├── remote/
│   ├── orchestrator/
│   │   ├── app.py
│   │   ├── routes/
│   │   │   └── robot_chat.py
│   │   └── services/
│   │       ├── robot_chat_service.py
│   │       ├── mode_manager.py
│   │       ├── mode_policy.py
│   │       ├── rag_router.py
│   │       ├── tts_service.py
│   │       └── robot_action_service.py
│   ├── qwen-server/
│   └── speech-service/
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
  "mode": "elderly",
  "input": {
    "type": "audio_base64",
    "audio_base64": "UklGRiQAAABXQVZFZm10IBAAAAABAAEA",
    "audio_format": "wav",
    "sample_rate": 16000,
    "channels": 1,
    "text_hint": "切换为老年模式"
  }
}
```

V1 测试里 `text_hint` 用来模拟 ASR 结果。真实 ASR 后续接入后，应由远端 ASR 结果触发同一套模式切换逻辑。

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

当前支持四种 session mode：

| mode | rag_namespace | speech_style |
| --- | --- | --- |
| `elderly` | `elderly_care` | `elderly_gentle` |
| `child` | `child_companion` | `child_playful` |
| `student` | `student_learning` | `student_focused` |
| `normal` | `general` | `normal` |

支持的口语命令包括：

```text
切换为老年模式 / 进入老年模式 / 老人模式
切换为儿童模式 / 进入儿童模式 / 孩子模式
切换为学生模式 / 进入学生模式 / 学习模式
切换为正常模式 / 普通模式
```

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
    "mode": "elderly",
    "input": {
      "type": "audio_base64",
      "audio_base64": "UklGRiQAAABXQVZFZm10IBAAAAABAAEA",
      "audio_format": "wav",
      "sample_rate": 16000,
      "channels": 1,
      "text_hint": "切换为儿童模式"
    }
  }'
```

## 检查 raspirobot

Pi 侧配置通过环境变量控制：

```bash
export ROBOT_REMOTE_BASE_URL=http://127.0.0.1:19000
export ROBOT_CHAT_ENDPOINT=/v1/robot/chat_turn
export ROBOT_REMOTE_TIMEOUT_SECONDS=40
export ROBOT_MODE_DEFAULT=elderly
export ROBOT_SESSION_ID=demo-session-001
```

最小导入检查：

```bash
cd fyfzsylxsRobot
python3 - <<'PY'
from raspirobot.state_machine import RobotStateMachine
from raspirobot.remote_client import RemoteClient, MockRemoteClient
from raspirobot.actions import DefaultRobotActionDispatcher

print(RobotStateMachine())
print(RemoteClient().url)
print(MockRemoteClient())
print(DefaultRobotActionDispatcher.with_mocks())
PY
```

启动 raspirobot skeleton health app：

```bash
cd fyfzsylxsRobot
uvicorn raspirobot.app:app --host 127.0.0.1 --port 18081
```

## 运行测试

```bash
cd fyfzsylxsRobot
python3 -m pytest tests/test_robot_skeleton.py tests/test_robot_chat_logic.py
```

如果当前机器没有安装 `pytest` 或 `pydantic`，先按项目环境安装依赖。V1 测试不需要 Raspberry Pi 硬件。

## 当前有意不实现的内容

本轮不实现：

- 真实麦克风录音；
- 真实摄像头采集；
- 真实扬声器播放；
- OLED SPI；
- PCA9685 / 舵机控制；
- 唤醒词引擎；
- 人脸跟踪算法；
- 完整 ASR/TTS/LLM/RAG；
- 数据库 session 存储；
- ROS2；
- avatar-service、lip-sync 或数字人视频输出。

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
