from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import Event, Lock, Thread
from time import monotonic, sleep
from typing import Any

from PIL import Image, ImageOps, ImageSequence

IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".bmp", ".webp")

# ST7789V 初始化序列（不含软件复位，硬件复位由 ST7789EyesDriver 统一管理）
_INIT_CMDS: list[tuple[int, list[int] | None]] = [
    (0x11, None),   # Sleep out
    (0x3A, [0x55]), # 16-bit color (RGB565)
    (0x36, [0x00]), # Memory access control
    (0x21, None),   # Display inversion on
    (0x29, None),   # Display on
]


@dataclass(frozen=True)
class ST7789EyeConfig:
    assets_dir: Path
    fps: int = 12
    width: int = 240
    height: int = 320
    rotation: int = 0
    spi_port: int = 0
    spi_speed_hz: int = 40_000_000
    dc_gpio: int = 25
    rst_gpio: int = 24
    left_cs: int = 0
    right_cs: int = 1
    right_enabled: bool = True
    mirror_right: bool = False
    gpio_chip: str = "/dev/gpiochip0"


class _ST7789Display:
    """单块 ST7789V 屏幕的底层驱动，使用 spidev + gpiod。"""

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
        gpio_chip: str,
        gpio_lines: Any,  # gpiod RequestLines 对象，由外部统一管理
    ) -> None:
        self.width = width
        self.height = height
        self._dc_gpio = dc_gpio
        self._rst_gpio = rst_gpio
        self._lines = gpio_lines

        import spidev
        import gpiod

        self._gpiod = gpiod
        self._spi = spidev.SpiDev()
        self._spi.open(spi_port, spi_cs)
        self._spi.max_speed_hz = spi_speed_hz
        self._spi.mode = 0

        # 复位由 ST7789EyesDriver 统一管理，这里只发初始化命令
        self._init()

    def display(self, image: Image.Image) -> None:
        """将 PIL Image 推送到屏幕，图像必须是 RGB 模式且尺寸匹配。"""
        self._set_window(0, 0, self.width - 1, self.height - 1)
        self._cmd(0x2C)
        # 转换为 RGB565
        pixels = self._to_rgb565(image)
        self._data_bytes(pixels)

    def close(self) -> None:
        self._spi.close()

    # ── 私有方法 ──────────────────────────────────────────

    def _reset(self) -> None:
        import time
        self._lines.set_value(self._rst_gpio, self._gpiod.line.Value.INACTIVE)
        time.sleep(0.1)
        self._lines.set_value(self._rst_gpio, self._gpiod.line.Value.ACTIVE)
        time.sleep(0.15)

    def _init(self) -> None:
        import time
        for cmd, data in _INIT_CMDS:
            self._cmd(cmd)
            if data:
                self._data(data)
            if cmd == 0x11:  # Sleep out 需要等待
                time.sleep(0.15)

    def _set_window(self, x0: int, y0: int, x1: int, y1: int) -> None:
        self._cmd(0x2A)
        self._data([x0 >> 8, x0 & 0xFF, x1 >> 8, x1 & 0xFF])
        self._cmd(0x2B)
        self._data([y0 >> 8, y0 & 0xFF, y1 >> 8, y1 & 0xFF])

    def _cmd(self, cmd: int) -> None:
        self._lines.set_value(self._dc_gpio, self._gpiod.line.Value.INACTIVE)
        self._spi.xfer2([cmd])

    def _data(self, data: list[int]) -> None:
        self._lines.set_value(self._dc_gpio, self._gpiod.line.Value.ACTIVE)
        self._spi.xfer2(data)

    def _data_bytes(self, data: bytes | bytearray) -> None:
        self._lines.set_value(self._dc_gpio, self._gpiod.line.Value.ACTIVE)
        chunk = 4096
        mv = memoryview(data)
        for i in range(0, len(data), chunk):
            self._spi.xfer2(mv[i:i + chunk].tolist())

    @staticmethod
    def _to_rgb565(image: Image.Image) -> bytearray:
        """将 RGB PIL Image 转换为 RGB565 字节流（大端序）。"""
        buf = bytearray(image.width * image.height * 2)
        idx = 0
        for r, g, b in image.getdata():
            pixel = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
            buf[idx] = (pixel >> 8) & 0xFF
            buf[idx + 1] = pixel & 0xFF
            idx += 2
        return buf


class ST7789EyesDriver:
    """双眼 ST7789V 驱动，使用 spidev + gpiod，兼容树莓派5。

    接口与原 Pimoroni st7789 版本完全相同：
        driver.set_expression("neutral")
        driver.close()
    """

    def __init__(self, config: ST7789EyeConfig) -> None:
        self.config = config
        self._lock = Lock()
        self._stop = Event()
        self._expression = "neutral"
        self._frame_index = 0
        self._last_expression = "neutral"
        self._frame_cache: dict[str, list[Image.Image]] = {}
        self._blank_frame = Image.new("RGB", (config.width, config.height), (0, 0, 0))

        self._gpio_lines = self._init_gpio()
        self._hardware_reset()  # 先统一复位两块屏
        self._left_display = self._build_display(cs=config.left_cs)
        self._right_display = (
            self._build_display(cs=config.right_cs) if config.right_enabled else None
        )

        self._render_thread = Thread(
            target=self._render_loop, name="st7789-eyes-render", daemon=True
        )
        self._render_thread.start()

    def set_expression(self, expression: str) -> None:
        normalized = (expression or "neutral").strip().lower() or "neutral"
        with self._lock:
            if normalized != self._expression:
                self._expression = normalized
                self._frame_index = 0

    def close(self) -> None:
        self._stop.set()
        self._render_thread.join(timeout=1.0)
        self._left_display.close()
        if self._right_display is not None:
            self._right_display.close()

    # ── 渲染循环 ──────────────────────────────────────────

    def _render_loop(self) -> None:
        frame_interval = 1.0 / max(1, self.config.fps)
        while not self._stop.is_set():
            started = monotonic()
            expression = self._get_expression()
            frames = self._frames_for_expression(expression)
            if not frames:
                frames = [self._blank_frame]

            if expression != self._last_expression:
                self._frame_index = 0
                self._last_expression = expression

            frame = frames[self._frame_index % len(frames)]
            self._frame_index += 1
            try:
                self._display_frame(frame)
            except Exception as e:
                import traceback
                traceback.print_exc()

            elapsed = monotonic() - started
            if elapsed < frame_interval:
                sleep(frame_interval - elapsed)

    def _get_expression(self) -> str:
        with self._lock:
            return self._expression

    def _display_frame(self, frame: Image.Image) -> None:
        self._left_display.display(frame)
        if self._right_display is None:
            return
        if self.config.mirror_right:
            self._right_display.display(ImageOps.mirror(frame))
        else:
            self._right_display.display(frame)

    # ── 素材加载 ──────────────────────────────────────────

    def _frames_for_expression(self, expression: str) -> list[Image.Image]:
        cached = self._frame_cache.get(expression)
        if cached is not None:
            return cached
        frames = self._load_frames(expression)
        self._frame_cache[expression] = frames
        return frames

    def _load_frames(self, expression: str) -> list[Image.Image]:
        primary = self._expression_asset(expression)
        fallback = self._expression_asset("neutral")
        asset = primary or fallback
        if asset is None:
            return [self._blank_frame]

        if asset.is_dir():
            files = sorted(
                path
                for path in asset.iterdir()
                if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
            )
            if not files:
                return [self._blank_frame]
            return [self._load_image(f) for f in files]

        suffix = asset.suffix.lower()
        if suffix == ".gif":
            return self._load_gif(asset)
        if suffix in IMAGE_SUFFIXES:
            return [self._load_image(asset)]
        return [self._blank_frame]

    def _expression_asset(self, expression: str) -> Path | None:
        base = self.config.assets_dir / expression
        if base.is_dir():
            return base
        candidates = [base.with_suffix(".gif")]
        candidates.extend(base.with_suffix(ext) for ext in IMAGE_SUFFIXES)
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None

    def _load_gif(self, path: Path) -> list[Image.Image]:
        frames: list[Image.Image] = []
        with Image.open(path) as image:
            for gif_frame in ImageSequence.Iterator(image):
                frames.append(self._fit_frame(gif_frame.convert("RGB")))
        return frames or [self._blank_frame]

    def _load_image(self, path: Path) -> Image.Image:
        with Image.open(path) as image:
            return self._fit_frame(image.convert("RGB"))

    def _fit_frame(self, frame: Image.Image) -> Image.Image:
        if frame.size == (self.config.width, self.config.height):
            return frame
        return ImageOps.fit(
            frame,
            (self.config.width, self.config.height),
            method=Image.Resampling.BICUBIC,
        )

    # ── 硬件初始化 ────────────────────────────────────────

    def _hardware_reset(self) -> None:
        """统一复位所有屏幕（共享 RST 引脚，一次复位同时作用于所有屏）。"""
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
            raise RuntimeError(
                "gpiod Python 包未安装。请运行: pip install gpiod"
            ) from exc

        gpio_pins = {self.config.dc_gpio, self.config.rst_gpio}
        return gpiod.request_lines(
            self.config.gpio_chip,
            consumer="st7789-eyes",
            config={
                tuple(gpio_pins): gpiod.LineSettings(
                    direction=gpiod.line.Direction.OUTPUT
                )
            },
        )

    def _build_display(self, *, cs: int) -> _ST7789Display:
        try:
            import spidev  # noqa: F401
        except ImportError as exc:
            raise RuntimeError(
                "spidev Python 包未安装。请运行: pip install spidev"
            ) from exc

        return _ST7789Display(
            spi_port=self.config.spi_port,
            spi_cs=cs,
            spi_speed_hz=self.config.spi_speed_hz,
            dc_gpio=self.config.dc_gpio,
            rst_gpio=self.config.rst_gpio,
            width=self.config.width,
            height=self.config.height,
            gpio_chip=self.config.gpio_chip,
            gpio_lines=self._gpio_lines,
        )
