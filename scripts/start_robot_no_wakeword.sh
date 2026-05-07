#!/bin/bash
# RobotMatch 启动脚本（不带唤醒词，直接监听）
# 使用方法：bash scripts/start_robot_no_wakeword.sh

cd /home/pi/Desktop/code/fyfzsylxsRobot
source /home/pi/Desktop/code/fyfzsylxsRobot/.venv/bin/activate

mkdir -p /home/pi/Desktop/code/fyfzsylxsRobot/tmp/wav

# ========================================
# 唤醒词配置（禁用）
# ========================================
export ROBOT_WAKE_WORD_ENABLED=false

# ========================================
# 语音链路
# ========================================
export ROBOT_REMOTE_BASE_URL=http://127.0.0.1:29000
export ROBOT_AUDIO_WORK_DIR=/home/pi/Desktop/code/fyfzsylxsRobot/tmp/wav
export ROBOT_AUDIO_CAPTURE_DEVICE=plughw:CARD=Lite,DEV=0
export ROBOT_AUDIO_PLAYBACK_DEVICE=plughw:CARD=Device,DEV=0
export ROBOT_AUDIO_SAMPLE_RATE=16000
export ROBOT_AUDIO_CHANNELS=2

# 设置音量
amixer -D plughw:CARD=Device,DEV=0 sset Master 70% 2>/dev/null || true

# ========================================
# 音频预处理
# ========================================
export ROBOT_AUDIO_PREPROCESS_ENABLED=true
export ROBOT_AUDIO_ENABLE_NOISE_GATE=true
export ROBOT_AUDIO_ENABLE_TRIM=true
export ROBOT_AUDIO_NOISE_GATE_RATIO=2.0
export ROBOT_AUDIO_POST_SPEECH_PADDING_MS=200
export ROBOT_AUDIO_MIN_SPEECH_MS=400
export ROBOT_AUDIO_SAVE_DEBUG_WAV=true
export ROBOT_AUDIO_POST_PLAYBACK_COOLDOWN_MS=800
export ROBOT_AUDIO_DROP_INVALID_UTTERANCE=true
export ROBOT_AUDIO_DROP_REASONS=no_speech_detected,speech_too_short

# ========================================
# OLED 眼睛屏
# ========================================
export ROBOT_EYES_PROVIDER=st7789
export ROBOT_EYES_ASSETS_DIR=raspirobot/assets/eyes
export ROBOT_EYES_LEFT_ASSETS_DIR=raspirobot/assets/eyes/left
export ROBOT_EYES_RIGHT_ASSETS_DIR=raspirobot/assets/eyes/right
export ROBOT_EYES_RIGHT_ENABLED=true
export ROBOT_EYES_SPI_PORT=0
export ROBOT_EYES_RIGHT_SPI_PORT=1
export ROBOT_EYES_RIGHT_CS=0
export ROBOT_EYES_RST_GPIO=22
export ROBOT_EYES_LEFT_DC_GPIO=25
export ROBOT_EYES_RIGHT_DC_GPIO=24
export ROBOT_EYES_LEFT_ROTATION=270
export ROBOT_EYES_RIGHT_ROTATION=270

# ========================================
# 视频链路（人脸识别）
# ========================================
export ROBOT_VISION_REMOTE_ENABLED=true
export ROBOT_VISION_INGEST_URL=http://127.0.0.1:29001/v1/video/ingest
export ROBOT_VISION_FROM_CACHE_URL=http://127.0.0.1:29002/v1/vision/identity/from-cache

# ========================================
# 日志
# ========================================
export ROBOT_LOG_LEVEL=INFO
export ROBOT_DEBUG_TRACE=true

# ========================================
# 启动信息
# ========================================
echo "========================================"
echo "  RobotMatch 机器人启动（直接监听）"
echo "========================================"
echo ""
echo "⚠️  唤醒词: 已禁用（直接监听模式）"
echo "✅ 远程服务: $ROBOT_REMOTE_BASE_URL"
echo "✅ 麦克风: $ROBOT_AUDIO_CAPTURE_DEVICE"
echo "✅ 扬声器: $ROBOT_AUDIO_PLAYBACK_DEVICE"
echo "✅ 眼睛屏: ST7789 双屏"
echo "✅ 人脸追踪: 已启用"
echo "✅ 视频上传: 已启用"
echo ""
echo "工作流程："
echo "  1. 直接监听 → 检测到语音"
echo "  2. 说话 → 处理 → 回复"
echo "  3. 继续监听下一轮"
echo ""
echo "按 Ctrl+C 停止"
echo "========================================"
echo ""

# ========================================
# 启动机器人
# ========================================
python -m raspirobot.main live \
  --face-track \
  --face-track-detector auto \
  --face-track-actuation-range 270 \
  --face-track-center-pan 135 --face-track-center-tilt 135 \
  --face-track-pan-min-angle 0 --face-track-pan-max-angle 270 \
  --face-track-tilt-min-angle 35 --face-track-tilt-max-angle 235
