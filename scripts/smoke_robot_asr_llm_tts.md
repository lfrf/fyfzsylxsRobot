# Robot ASR/LLM/TTS Smoke

After remote services are running and the Raspberry Pi tunnel is open:

```bash
cd fyfzsylxsRobot
source .venv/bin/activate
export ROBOT_REMOTE_BASE_URL=http://127.0.0.1:29000
python -m raspirobot.scripts.audio_tunnel_smoke --wav /tmp/robot_test.wav
```

Expected response fields:

```text
asr_text=...
reply_text=...
tts_audio_url=/v1/robot/media/tts/...
```

If `tts_audio_url` is `mock://...`, the orchestrator is still in mock TTS mode.

To test playback:

```bash
export ROBOT_AUDIO_PLAYBACK_DEVICE=plughw:3,0
python -m raspirobot.scripts.audio_tunnel_smoke --wav /tmp/robot_test.wav --play
```
