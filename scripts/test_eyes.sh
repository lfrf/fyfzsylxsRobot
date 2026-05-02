#!/bin/bash
# 眼睛表情屏幕测试脚本
# 在树莓派上运行：bash scripts/test_eyes.sh

cd /home/pi/Desktop/code/fyfzsylxsRobot
source .venv/bin/activate

export ROBOT_EYES_PROVIDER=st7789
export ROBOT_EYES_ASSETS_DIR=/home/pi/Desktop/code/fyfzsylxsRobot/raspirobot/assets/eyes
export ROBOT_EYES_FRAME_FPS=12
export ROBOT_EYES_SCREEN_WIDTH=240
export ROBOT_EYES_SCREEN_HEIGHT=320
export ROBOT_EYES_ROTATION=0
export ROBOT_EYES_SPI_PORT=0
export ROBOT_EYES_SPI_SPEED_HZ=40000000
export ROBOT_EYES_DC_GPIO=25
export ROBOT_EYES_RST_GPIO=24
export ROBOT_EYES_LEFT_CS=0
export ROBOT_EYES_RIGHT_CS=1
export ROBOT_EYES_RIGHT_ENABLED=true

python -m raspirobot.scripts.st7789_eyes_demo --expressions neutral --hold-seconds 5
