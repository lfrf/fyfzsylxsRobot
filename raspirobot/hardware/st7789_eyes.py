from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import Event, Lock, Thread
from time import monotonic, sleep
from typing import Any

from PIL import Image, ImageOps, ImageSequence

IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".bmp", ".webp", ".gif")

# ST7789V 初始化序列（不含软件复位）
# MADCTL=0x00: 从左到右、从上到下扫描，与 SPI 写入方向一致，最小化撕裂
_INIT_CMDS: list[tuple[int, list[int] | None]] = [
    (0x11, None),    # Sleep out
    (0x3A, [0x55]),  # 16-bit color (RGB565)
    (0x36, [0x00]),  # Memory access control: top-to-bottom, left-to-right
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
    left_rotation: int = 270                # 左眼素材旋转角度（横放屏幕）
    right_rotation: int = 90                # 右眼素材旋转角度（横放屏幕）
    left_phase_offset_ms: int = 0           # 正数=左眼动画延后，负数=提前
    right_phase_offset_ms: int = 0          # 正数=右眼动画延后，负数=提前

    def get_left_assets_dir(self) -> Path:
        return self.left_assets_dir or self.assets_dir

    def get_right_assets_dir(self) -> Path:
        return self.right_assets_dir or self.assets_dir


class _SharedAnimationClock:
    """为左右眼提供共享的帧时钟，避免各自线程独立累加 frame_index 导致相位漂移。"""

    def __init__(self, fps: int) -> None:
        self._fps = max(1, fps)
        self._lock = Lock()
        self._expression_started_at: dict[str, float] = {}

    def reset_expression(self, expression: str) -> None:
        with self._lock:
            self._expression_started_at[(expression or "neutral").strip().lower() or "neutral"] = monotonic()

    def frame_index_for(self, expression: str, frame_count: int, phase_offset_ms: int = 0) -> int:
        if frame_count <= 1:
            return 0
        normalized = (expression or "neutral").strip().lower() or "neutral"
        now = monotonic()
        with self._lock:
            started_at = self._expression_started_at.get(normalized)
            if started_at is None:
                started_at = now
                self._expression_started_at[normalized] = started_at
        elapsed = max(0.0, now - started_at - (phase_offset_ms / 1000.0))
        return int(elapsed * self._fps) % frame_count


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
        animation_clock: _SharedAnimationClock | None = None,
        phase_offset_ms: int = 0,
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
        self._animation_clock = animation_clock
        self._phase_offset_ms = phase_offset_ms

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

        # 局部刷新区域：只刷新眼睛内容所在的区域，减少传输数据量
        # 在旋转后的坐标系中，眼睛内容约在中心 192×192 区域
        pad = 8  # 边距
        cx, cy = width // 2, height // 2
        half = 96 + pad  # 192/2 + 边距
        self._partial_rect: tuple[int, int, int, int] | None = (
            max(0, cx - half),
            max(0, cy - half),
            min(width - 1, cx + half - 1),
            min(height - 1, cy + half - 1),
        )
        px0, py0, px1, py1 = self._partial_rect
        self._partial_w = px1 - px0 + 1
        self._partial_h = py1 - py0 + 1
        self._blank = bytearray(self._partial_w * self._partial_h * 2)

        # 初始化屏幕（复位已由外部统一完成），先整屏清黑一次，避免局部刷新外的区域保留随机显存。
        self._init()
        self._clear_screen()

    def set_expression(self, expression: str) -> None:
        normalized = (expression or "neutral").strip().lower() or "neutral"
        changed = False
        with self._lock:
            if normalized != self._expression:
                self._expression = normalized
                self._frame_index = 0
                changed = True
        if changed and self._animation_clock is not None:
            self._animation_clock.reset_expression(normalized)

    def close(self) -> None:
        self._spi.close()

    # ── 渲染辅助 ──────────────────────────────────────────

    def next_frame(self) -> bytearray:
        with self._lock:
            expression = self._expression

        frames = self._frames_for_expression(expression)
        if not frames:
            frames = [self._blank]

        if expression != self._last_expression:
            self._frame_index = 0
            self._last_expression = expression
            if self._animation_clock is not None:
                self._animation_clock.reset_expression(expression)

        if self._animation_clock is not None:
            self._frame_index = self._animation_clock.frame_index_for(
                expression,
                len(frames),
                phase_offset_ms=self._phase_offset_ms,
            )
            return frames[self._frame_index]

        frame = frames[self._frame_index % len(frames)]
        self._frame_index += 1
        return frame

    def send_frame_if_changed(self, frame: bytearray) -> bool:
        last_sent = getattr(self, "_last_sent", None)
        if frame is last_sent:
            return False
        self._send_frame(frame)
        self._last_sent = frame
        return True

    def _clear_screen(self) -> None:
        full_black = bytearray(self.width * self.height * 2)
        self._set_window(0, 0, self.width - 1, self.height - 1)
        self._cmd(0x2C)
        self._data_bytes(full_black)
        self._lines.set_value(self._dc_gpio, self._gpiod.line.Value.INACTIVE)

    def _send_frame(self, frame: bytes | bytearray) -> None:
        """frame 是预转换好的 RGB565 字节流，支持全帧或局部帧。"""
        t0 = monotonic()
        if hasattr(self, '_partial_rect') and self._partial_rect is not None:
            x0, y0, x1, y1 = self._partial_rect
            self._set_window(x0, y0, x1, y1)
        else:
            self._set_window(0, 0, self.width - 1, self.height - 1)
        self._cmd(0x2C)
        self._data_bytes(frame)
        self._lines.set_value(self._dc_gpio, self._gpiod.line.Value.INACTIVE)
        # 让总传输时间凑成 16ms 的整数倍（48ms = 16×3）
        # 撕裂线会固定在同一位置，视觉上不再移动
        elapsed = (monotonic() - t0) * 1000
        target_ms = 48.0
        remaining = target_ms - elapsed
        if remaining > 0:
            sleep(remaining / 1000.0)

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
            if not files:
                return [self._blank]
            frames: list[bytearray] = []
            for f in files:
                if f.suffix.lower() == ".gif":
                    frames.extend(self._load_gif(f))
                else:
                    frames.append(self._load_image(f))
            return frames if frames else [self._blank]

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
        # 先缩放到全屏尺寸
        if frame.size != (self.width, self.height):
            frame = ImageOps.fit(frame, (self.width, self.height), method=Image.Resampling.BICUBIC)
        # 再裁剪到局部刷新区域
        if self._partial_rect is not None:
            x0, y0, x1, y1 = self._partial_rect
            frame = frame.crop((x0, y0, x1 + 1, y1 + 1))
        return frame

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
        self._spi.writebytes2(data)

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


class _LegacyGPIOLines:
    def __init__(self, gpio_module: Any, gpio_chip: str, gpio_pins: set[int], consumer: str) -> None:
        self._gpiod = gpio_module
        self._chip = gpio_module.Chip(gpio_chip)
        self._lines: dict[int, Any] = {}
        for pin in sorted(gpio_pins):
            line = self._chip.get_line(pin)
            line.request(consumer=consumer, type=self._gpiod.LINE_REQ_DIR_OUT, default_vals=[0])
            self._lines[pin] = line

    def set_value(self, pin: int, value: Any) -> None:
        line = self._lines[pin]
        if hasattr(self._gpiod, "line") and hasattr(self._gpiod.line, "Value"):
            if value == self._gpiod.line.Value.ACTIVE:
                line.set_value(1)
                return
            if value == self._gpiod.line.Value.INACTIVE:
                line.set_value(0)
                return
        line.set_value(1 if value else 0)

    def close(self) -> None:
        for line in self._lines.values():
            try:
                line.release()
            except Exception:
                pass
        try:
            self._chip.close()
        except Exception:
            pass


class ST7789EyesDriver:
    """双眼 ST7789V 驱动。

    左右眼各有独立 DC 引脚和独立素材目录，由统一渲染线程调度刷新。
    """

    def __init__(self, config: ST7789EyeConfig) -> None:
        self.config = config
        self._gpio_lines = self._init_gpio()
        self._hardware_reset()
        self._animation_clock = _SharedAnimationClock(config.fps)
        self._stop = Event()
        self._send_left_first = True

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
            animation_clock=self._animation_clock,
            phase_offset_ms=config.left_phase_offset_ms,
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
                animation_clock=self._animation_clock,
                phase_offset_ms=config.right_phase_offset_ms,
            )

        self._thread = Thread(target=self._render_loop, name="st7789-eyes", daemon=True)
        self._thread.start()

    def set_expression(self, expression: str) -> None:
        self._left.set_expression(expression)
        if self._right is not None:
            self._right.set_expression(expression)

    def close(self) -> None:
        self._stop.set()
        self._thread.join(timeout=2.0)
        self._left.close()
        if self._right is not None:
            self._right.close()

    def _render_loop(self) -> None:
        frame_interval = 1.0 / max(1, self.config.fps)
        while not self._stop.is_set():
            started = monotonic()
            left_frame = self._left.next_frame()
            right_frame = self._right.next_frame() if self._right is not None else None

            try:
                if self._right is None:
                    self._left.send_frame_if_changed(left_frame)
                elif self._send_left_first:
                    self._left.send_frame_if_changed(left_frame)
                    self._right.send_frame_if_changed(right_frame)
                else:
                    self._right.send_frame_if_changed(right_frame)
                    self._left.send_frame_if_changed(left_frame)
            except Exception:
                import traceback
                traceback.print_exc()

            self._send_left_first = not self._send_left_first
            elapsed = monotonic() - started
            if elapsed < frame_interval:
                sleep(frame_interval - elapsed)

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
