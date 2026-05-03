from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from queue import Empty, Queue
from threading import Event, Lock, Thread
from time import monotonic, sleep
from typing import Any

from PIL import Image, ImageOps, ImageSequence

IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".bmp", ".webp")

# ST7789V 初始化序列（不含软件复位）
_INIT_CMDS: list[tuple[int, list[int] | None]] = [
    (0x11, None),    # Sleep out
    (0x3A, [0x55]),  # 16-bit color (RGB565)
    (0x36, [0x00]),  # Memory access control
    (0x21, None),    # Display inversion on
    (0x29, None),    # Display on
]


@dataclass(frozen=True)
class ST7789EyeConfig:
    assets_dir: Path                        # 兼容旧配置，作为左眼素材目录的默认值
    fps: int = 12
    width: int = 240
    height: int = 320
    rotation: int = 0
    spi_port: int = 0                       # 左眼 SPI 端口
    right_spi_port: int = 1                 # 右眼 SPI 端口（独立总线）
    spi_speed_hz: int = 40_000_000
    rst_gpio: int = 22                      # 共享复位引脚
    left_dc_gpio: int = 25                  # 左眼独立 DC
    right_dc_gpio: int = 24                 # 右眼独立 DC
    left_cs: int = 0
    right_cs: int = 0                       # SPI1 只有一个 CS，用 0
    right_enabled: bool = True
    left_assets_dir: Path | None = None
    right_assets_dir: Path | None = None
    gpio_chip: str = "/dev/gpiochip0"
    left_rotation: int = 90                 # 左眼素材旋转角度（横放屏幕）
    right_rotation: int = 90                # 右眼素材旋转角度（横放屏幕）

    def get_left_assets_dir(self) -> Path:
        return self.left_assets_dir or self.assets_dir

    def get_right_assets_dir(self) -> Path:
        return self.right_assets_dir or self.assets_dir


class _ST7789Display:
    """单块 ST7789V 屏幕，有独立的 DC 引脚、素材目录和渲染线程。"""

    def __init__(
        self,
        *,
        spi_port: int,
        spi_cs: int,
        spi_speed_hz: int,
        dc_gpio: int,
        rst_gpio: int,
        width: int,
        height: int,
        assets_dir: Path,
        fps: int,
        gpio_lines: Any,
        name: str = "eye",
        img_rotation: int = 0,
    ) -> None:
        self.width = width
        self.height = height
        self.assets_dir = assets_dir
        self._dc_gpio = dc_gpio
        self._rst_gpio = rst_gpio
        self._lines = gpio_lines
        self._name = name
        self._fps = fps
        self._img_rotation = img_rotation

        import spidev
        import gpiod

        self._gpiod = gpiod
        self._spi = spidev.SpiDev()
        self._spi.open(spi_port, spi_cs)
        self._spi.max_speed_hz = spi_speed_hz
        self._spi.mode = 0

        self._blank: bytearray = bytearray(width * height * 2)  # 全黑预转换帧
        self._frame_cache: dict[str, list[bytearray]] = {}
        self._expression = "neutral"
        self._frame_index = 0
        self._last_expression = "neutral"
        self._lock = Lock()
        self._queue: Queue[bytearray | None] = Queue(maxsize=2)
        self._stop = Event()

        # 初始化屏幕（复位已由外部统一完成）
        self._init()

        # 启动独立渲染线程
        self._thread = Thread(target=self._render_loop, name=f"st7789-{name}", daemon=True)
        self._thread.start()

    def set_expression(self, expression: str) -> None:
        normalized = (expression or "neutral").strip().lower() or "neutral"
        with self._lock:
            if normalized != self._expression:
                self._expression = normalized
                self._frame_index = 0

    def close(self) -> None:
        self._stop.set()
        try:
            self._queue.put_nowait(None)
        except Exception:
            pass
        self._thread.join(timeout=2.0)
        self._spi.close()

    # ── 渲染线程 ──────────────────────────────────────────

    def _render_loop(self) -> None:
        frame_interval = 1.0 / max(1, self._fps)
        last_sent: bytes | None = None
        while not self._stop.is_set():
            started = monotonic()

            with self._lock:
                expression = self._expression

            frames = self._frames_for_expression(expression)
            if not frames:
                frames = [self._blank]

            if expression != self._last_expression:
                self._frame_index = 0
                self._last_expression = expression

            frame = frames[self._frame_index % len(frames)]
            self._frame_index += 1

            # 只有帧内容变化时才发送，减少持续撕裂
            if frame is not last_sent:
                try:
                    self._send_frame(frame)
                    last_sent = frame
                except Exception:
                    import traceback
                    traceback.print_exc()

            elapsed = monotonic() - started
            if elapsed < frame_interval:
                sleep(frame_interval - elapsed)

    def _send_frame(self, frame: bytes | bytearray) -> None:
        """frame 是预转换好的 RGB565 字节流。"""
        self._set_window(0, 0, self.width - 1, self.height - 1)
        self._cmd(0x2C)
        self._data_bytes(frame)
        self._lines.set_value(self._dc_gpio, self._gpiod.line.Value.INACTIVE)

    # ── 素材加载 ──────────────────────────────────────────

    def _frames_for_expression(self, expression: str) -> list[Image.Image]:
        cached = self._frame_cache.get(expression)
        if cached is not None:
            return cached
        frames = self._load_frames(expression)
        self._frame_cache[expression] = frames
        return frames

    def _load_frames(self, expression: str) -> list[Image.Image]:
        asset = self._expression_asset(expression) or self._expression_asset("neutral")
        if asset is None:
            return [self._blank]

        if asset.is_dir():
            files = sorted(
                p for p in asset.iterdir()
                if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES
            )
            return [self._load_image(f) for f in files] if files else [self._blank]

        suffix = asset.suffix.lower()
        if suffix == ".gif":
            return self._load_gif(asset)
        if suffix in IMAGE_SUFFIXES:
            return [self._load_image(asset)]
        return [self._blank]

    def _expression_asset(self, expression: str) -> Path | None:
        base = self.assets_dir / expression
        if base.is_dir():
            return base
        for ext in [".gif"] + list(IMAGE_SUFFIXES):
            candidate = base.with_suffix(ext)
            if candidate.exists():
                return candidate
        return None

    def _load_gif(self, path: Path) -> list[bytearray]:
        frames: list[bytearray] = []
        with Image.open(path) as image:
            for gif_frame in ImageSequence.Iterator(image):
                frames.append(self._to_rgb565(self._fit_frame(gif_frame.convert("RGB"))))
        return frames or [self._blank]

    def _load_image(self, path: Path) -> bytearray:
        with Image.open(path) as image:
            return self._to_rgb565(self._fit_frame(image.convert("RGB")))

    def _fit_frame(self, frame: Image.Image) -> Image.Image:
        if self._img_rotation:
            frame = frame.rotate(-self._img_rotation, expand=True)
        if frame.size == (self.width, self.height):
            return frame
        return ImageOps.fit(frame, (self.width, self.height), method=Image.Resampling.BICUBIC)

    # ── 硬件操作 ──────────────────────────────────────────

    def _init(self) -> None:
        import time
        for cmd, data in _INIT_CMDS:
            self._cmd(cmd)
            if data:
                self._data(data)
            if cmd == 0x11:
                time.sleep(0.15)

    def _set_window(self, x0: int, y0: int, x1: int, y1: int) -> None:
        self._cmd(0x2A)
        self._data([x0 >> 8, x0 & 0xFF, x1 >> 8, x1 & 0xFF])
        self._cmd(0x2B)
        self._data([y0 >> 8, y0 & 0xFF, y1 >> 8, y1 & 0xFF])

    def _cmd(self, cmd: int) -> None:
        self._lines.set_value(self._dc_gpio, self._gpiod.line.Value.INACTIVE)
        self._spi.writebytes2(bytearray([cmd]))

    def _data(self, data: list[int]) -> None:
        self._lines.set_value(self._dc_gpio, self._gpiod.line.Value.ACTIVE)
        self._spi.writebytes2(bytearray(data))

    def _data_bytes(self, data: bytes | bytearray) -> None:
        self._lines.set_value(self._dc_gpio, self._gpiod.line.Value.ACTIVE)
        # SPI1 (spi-bcm2835aux) 单次传输有字节数限制，分块传输
        chunk = 65535
        for i in range(0, len(data), chunk):
            self._spi.writebytes2(data[i:i + chunk])

    @staticmethod
    def _to_rgb565(image: Image.Image) -> bytearray:
        try:
            import numpy as np
            arr = np.array(image, dtype=np.uint16)
            r = (arr[:, :, 0] >> 3).astype(np.uint16)
            g = (arr[:, :, 1] >> 2).astype(np.uint16)
            b = (arr[:, :, 2] >> 3).astype(np.uint16)
            rgb565 = (r << 11) | (g << 5) | b
            # 大端序
            high = (rgb565 >> 8).astype(np.uint8)
            low = (rgb565 & 0xFF).astype(np.uint8)
            interleaved = np.empty((image.height, image.width, 2), dtype=np.uint8)
            interleaved[:, :, 0] = high
            interleaved[:, :, 1] = low
            return bytearray(interleaved.tobytes())
        except ImportError:
            # fallback: 纯 Python
            buf = bytearray(image.width * image.height * 2)
            idx = 0
            for r, g, b in image.getdata():
                pixel = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
                buf[idx] = (pixel >> 8) & 0xFF
                buf[idx + 1] = pixel & 0xFF
                idx += 2
            return buf


class ST7789EyesDriver:
    """双眼 ST7789V 驱动。

    左右眼各有独立 DC 引脚、独立素材目录、独立渲染线程，完全并行。
    """

    def __init__(self, config: ST7789EyeConfig) -> None:
        self.config = config
        self._gpio_lines = self._init_gpio()
        self._hardware_reset()

        self._left = _ST7789Display(
            spi_port=config.spi_port,
            spi_cs=config.left_cs,
            spi_speed_hz=config.spi_speed_hz,
            dc_gpio=config.left_dc_gpio,
            rst_gpio=config.rst_gpio,
            width=config.width,
            height=config.height,
            assets_dir=config.get_left_assets_dir(),
            fps=config.fps,
            gpio_lines=self._gpio_lines,
            name="left",
            img_rotation=config.left_rotation,
        )

        self._right: _ST7789Display | None = None
        if config.right_enabled:
            self._right = _ST7789Display(
                spi_port=config.right_spi_port,
                spi_cs=config.right_cs,
                spi_speed_hz=config.spi_speed_hz,
                dc_gpio=config.right_dc_gpio,
                rst_gpio=config.rst_gpio,
                width=config.width,
                height=config.height,
                assets_dir=config.get_right_assets_dir(),
                fps=config.fps,
                gpio_lines=self._gpio_lines,
                name="right",
                img_rotation=config.right_rotation,
            )

    def set_expression(self, expression: str) -> None:
        self._left.set_expression(expression)
        if self._right is not None:
            self._right.set_expression(expression)

    def close(self) -> None:
        self._left.close()
        if self._right is not None:
            self._right.close()

    # ── 硬件初始化 ────────────────────────────────────────

    def _hardware_reset(self) -> None:
        import time
        import gpiod
        self._gpio_lines.set_value(self.config.rst_gpio, gpiod.line.Value.INACTIVE)
        time.sleep(0.1)
        self._gpio_lines.set_value(self.config.rst_gpio, gpiod.line.Value.ACTIVE)
        time.sleep(0.15)

    def _init_gpio(self) -> Any:
        try:
            import gpiod
        except ImportError as exc:
            raise RuntimeError("gpiod 未安装，请运行: pip install gpiod") from exc

        gpio_pins = {
            self.config.rst_gpio,
            self.config.left_dc_gpio,
            self.config.right_dc_gpio,
        }
        return gpiod.request_lines(
            self.config.gpio_chip,
            consumer="st7789-eyes",
            config={
                tuple(gpio_pins): gpiod.LineSettings(
                    direction=gpiod.line.Direction.OUTPUT
                )
            },
        )
