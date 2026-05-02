from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import Event, Lock, Thread
from time import monotonic, sleep
from typing import Any

from PIL import Image, ImageOps, ImageSequence

IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".bmp", ".webp")


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


class ST7789EyesDriver:
    def __init__(self, config: ST7789EyeConfig) -> None:
        self.config = config
        self._lock = Lock()
        self._stop = Event()
        self._expression = "neutral"
        self._frame_index = 0
        self._last_expression = "neutral"
        self._frame_cache: dict[str, list[Image.Image]] = {}
        self._blank_frame = Image.new("RGB", (config.width, config.height), (0, 0, 0))

        st7789 = self._import_st7789()
        self._left_display = self._build_display(st7789, cs=config.left_cs)
        self._right_display = (
            self._build_display(st7789, cs=config.right_cs) if config.right_enabled else None
        )

        self._render_thread = Thread(target=self._render_loop, name="st7789-eyes-render", daemon=True)
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
            self._display_frame(frame)

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
            return
        self._right_display.display(frame)

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
                [
                    path
                    for path in asset.iterdir()
                    if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
                ]
            )
            if not files:
                return [self._blank_frame]
            return [self._load_image(file) for file in files]

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
                frame = gif_frame.convert("RGB")
                frames.append(self._fit_frame(frame))
        return frames or [self._blank_frame]

    def _load_image(self, path: Path) -> Image.Image:
        with Image.open(path) as image:
            return self._fit_frame(image.convert("RGB"))

    def _fit_frame(self, frame: Image.Image) -> Image.Image:
        if frame.size == (self.config.width, self.config.height):
            return frame
        return ImageOps.fit(frame, (self.config.width, self.config.height), method=Image.Resampling.BICUBIC)

    def _build_display(self, st7789: Any, *, cs: int) -> Any:
        # Pimoroni st7789 1.0.1: port, cs, dc are positional args
        return st7789.ST7789(
            self.config.spi_port,
            cs,
            self.config.dc_gpio,
            rst=self.config.rst_gpio,
            width=self.config.width,
            height=self.config.height,
            rotation=self.config.rotation,
            spi_speed_hz=self.config.spi_speed_hz,
        )

    @staticmethod
    def _import_st7789() -> Any:
        try:
            import st7789  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "ROBOT_EYES_PROVIDER=st7789 but Python package 'st7789' is missing. "
                "Install it on Raspberry Pi with: pip install st7789"
            ) from exc
        return st7789
