# robot-runtime

Minimal local runtime for the desktop robot node (Raspberry Pi side).

## Responsibilities
- forward text/audio/video payloads to `edge-backend`
- map response emotion/action to:
  - dual OLED eye expression
  - 2-DOF head pose
  - local speaker hook

## Current Mode
- default hardware mode is `mock`
- no physical driver calls are made unless you implement hardware mode blocks

## Local Run (native Python)
```bash
cd local/robot-runtime
python -m pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 18100
```

## Docker Run
```bash
docker compose -f compose.yaml -f compose.robot.yaml up -d edge-backend robot-runtime
```

## API Quick Test
```bash
curl -s http://127.0.0.1:18100/health

curl -X POST http://127.0.0.1:18100/v1/chat/text \
  -H "Content-Type: application/json" \
  -d '{"text":"hello robot"}'
```

## Environment Variables
- `EDGE_BACKEND_BASE` default: `http://127.0.0.1:8000`
- `ROBOT_EYES_MODE` default: `mock`
- `ROBOT_SERVO_MODE` default: `mock`
- `ROBOT_AUDIO_MODE` default: `mock`
- `ROBOT_SERVO_MIN_DEGREE` default: `70`
- `ROBOT_SERVO_MAX_DEGREE` default: `110`
