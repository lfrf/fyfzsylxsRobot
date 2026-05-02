#!/bin/bash
# 眼睛表情屏幕测试脚本
# 在树莓派上运行：bash scripts/test_eyes.sh

cd /home/pi/Desktop/code/fyfzsylxsRobot
source .venv/bin/activate

export PYTHONPATH=/home/pi/Desktop/code/fyfzsylxsRobot

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
export ROBOT_EYES_MIRROR_RIGHT=false
export ROBOT_EYES_GPIO_CHIP=/dev/gpiochip0
export ROBOT_EYES_RST_GPIO=22
export ROBOT_EYES_LEFT_DC_GPIO=25
export ROBOT_EYES_RIGHT_DC_GPIO=24

echo "=== 检查 st7789 包 ==="
python -c "import st7789; print('st7789 OK:', st7789.__file__)" 2>&1 || echo "st7789 包未安装"

echo ""
echo "=== 检查 SPI 设备 ==="
ls /dev/spidev* 2>&1 || echo "SPI 设备不存在，请先开启 SPI"

echo ""
echo "=== 检查驱动初始化 ==="
python -c "
from raspirobot.config import load_settings
from raspirobot.main import build_eyes_driver
s = load_settings()
print('provider:', s.eyes_provider)
print('assets_dir:', s.eyes_assets_dir)
eyes = build_eyes_driver(s)
print('driver type:', type(eyes).__name__)
" 2>&1

echo ""
echo "=== 运行眼睛 demo ==="
python -m raspirobot.scripts.st7789_eyes_demo --expressions neutral --hold-seconds 5
