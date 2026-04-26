# Desktop Robot V1 - Runtime Architecture and Startup

## 1. Runtime Objective
- Remove digital avatar rendering chain for lower latency.
- Keep remote inference services as-is.
- Run robot local loop on Raspberry Pi:
  - capture
  - command forwarding
  - actuator expression

## 2. Service Graph
```
Robot (Raspberry Pi)
  robot-runtime  --->  edge-backend  --->  remote orchestrator/qwen/speech/vision
       |                    |
       +--> OLED eyes       +--> business contract normalization
       +--> head servos
       +--> speaker
```

## 3. Deployment Modes

### 3.1 Recommended for early integration
- On Raspberry Pi:
  - `edge-backend` (container)
  - `robot-runtime` (container)
- On remote server:
  - `scripts/remote/start_remote_stack_tmux.sh`
  - keep `AVATAR_SERVICE_ENABLED=false` in orchestrator env

### 3.2 Later optimization
- Move `robot-runtime` to native Python service for lower latency and direct GPIO access.
- Keep `edge-backend` containerized or move native as needed.

## 4. New Local Compose File
- Use:
  - `compose.yaml`
  - `compose.robot.yaml`
- Start:
```bash
docker compose -f compose.yaml -f compose.robot.yaml up -d edge-backend robot-runtime
```

## 5. Health Validation
```bash
curl -s http://127.0.0.1:8000/health
curl -s http://127.0.0.1:18100/health
```

## 6. End-to-End Test
```bash
curl -X POST http://127.0.0.1:18100/v1/chat/text \
  -H "Content-Type: application/json" \
  -d "{\"text\":\"Hello, can you hear me?\"}"
```

Expected:
- JSON response from robot-runtime
- Eyes expression and head command updated in runtime state
- Audio play hook called (mock by default)

## 7. Remote Startup (unchanged)
```bash
cd /root/autodl-tmp/a22/code/FuChuangSai_A22
./scripts/remote/stop_remote_stack_tmux.sh
./scripts/remote/start_remote_stack_tmux.sh
```

## 8. Future Upgrade Hooks
- add wake-word front-end process
- add VAD and turn segmentation on Pi
- add serial motor controller profile
- add persistent state telemetry channel
