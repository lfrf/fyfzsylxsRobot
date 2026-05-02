# 树莓派 ST7789 双眼屏接线与播放指南

你的模块参数是 `240x320`、`SPI`、`ST7789V`，这是 **TFT 彩屏**（不是 OLED）。

## 1. 建议线材与供电

- 线材：`2.54mm 杜邦线 母-母`（树莓派 40Pin 是公针，屏模块通常也是公针）
- 每块屏至少 7 根线，两块屏建议买 `20~30 根` 备份
- 供电建议：先用 `5V` 给屏（模块标注支持 3V~5V），逻辑仍走树莓派 3.3V GPIO

## 2. 双屏接线（左右眼）

两块屏共享 SPI 时钟/数据与 DC/RST，分别使用不同 CS。

| 屏引脚 | 左眼接树莓派 | 右眼接树莓派 | 说明 |
|---|---|---|---|
| GND | Pin 6 (GND) | Pin 9 (GND) | 地 |
| VCC | Pin 2 (5V) | Pin 4 (5V) | 电源 |
| SCL | Pin 23 (GPIO11/SCLK) | 同左眼 | SPI 时钟 |
| SDA | Pin 19 (GPIO10/MOSI) | 同左眼 | SPI 数据 |
| RST | Pin 18 (GPIO24) | 同左眼 | 复位 |
| DC | Pin 22 (GPIO25) | 同左眼 | 命令/数据 |
| CS | Pin 24 (GPIO8/CE0) | Pin 26 (GPIO7/CE1) | 左右片选 |

不需要连接 `MISO`（这个屏只写入）。

## 3. 开启 SPI

在树莓派执行：

```bash
sudo raspi-config
```

`Interface Options -> SPI -> Enable`，然后重启。

## 4. 准备动画素材

代码支持两种表达素材结构（目录来自 `ROBOT_EYES_ASSETS_DIR`）：

1. `neutral/000.png, 001.png...`（推荐）
2. `neutral.gif`（会自动拆帧播放）

例如：

```text
/tmp/raspirobot_eyes/
  neutral/
    000.png
    001.png
  happy/
    000.png
    001.png
  blink.gif
```

如果你手里是 mp4，可以先转帧：

```bash
mkdir -p /tmp/raspirobot_eyes/neutral
ffmpeg -i neutral.mp4 -vf "fps=12,scale=240:320:force_original_aspect_ratio=increase,crop=240:320" /tmp/raspirobot_eyes/neutral/%03d.png
```

## 5. 环境变量

```bash
export ROBOT_EYES_PROVIDER=st7789
export ROBOT_EYES_ASSETS_DIR=/tmp/raspirobot_eyes
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
```

## 6. 安装依赖并测试

```bash
cd fyfzsylxsRobot
bash scripts/setup_raspi_venv.sh
source .venv/bin/activate
python -m raspirobot.scripts.st7789_eyes_demo --expressions neutral happy blink --hold-seconds 2
```

如果要让主程序联动表情，正常启动 `raspirobot` 即可，`robot_action.expression` 会驱动屏幕切换。
