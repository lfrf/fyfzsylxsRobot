from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw

W = 240
H = 320
BG = (0, 0, 0)
WHITE = (245, 245, 245)
BLACK = (10, 10, 10)


def _canvas() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (W, H), BG)
    return img, ImageDraw.Draw(img)


def _draw_eye_base(draw: ImageDraw.ImageDraw) -> tuple[tuple[int, int, int, int], tuple[int, int, int, int]]:
    left = (38, 110, 102, 174)
    right = (138, 110, 202, 174)
    draw.ellipse(left, fill=WHITE)
    draw.ellipse(right, fill=WHITE)
    return left, right


def _draw_pupil(draw: ImageDraw.ImageDraw, eye_box: tuple[int, int, int, int], dx: int = 0, dy: int = 0) -> None:
    x1, y1, x2, y2 = eye_box
    cx = (x1 + x2) // 2 + dx
    cy = (y1 + y2) // 2 + dy
    r = 10
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=BLACK)


def _neutral_frame(i: int) -> Image.Image:
    img, draw = _canvas()
    left, right = _draw_eye_base(draw)
    offsets = [(-2, 0), (0, 0), (2, 0), (0, 1), (0, -1), (1, 0)]
    dx, dy = offsets[i % len(offsets)]
    _draw_pupil(draw, left, dx, dy)
    _draw_pupil(draw, right, dx, dy)
    return img


def _happy_frame(i: int) -> Image.Image:
    img, draw = _canvas()
    left_arc = (30, 120, 110, 188)
    right_arc = (130, 120, 210, 188)
    width = 7 + (i % 2)
    draw.arc(left_arc, start=200, end=340, fill=WHITE, width=width)
    draw.arc(right_arc, start=200, end=340, fill=WHITE, width=width)
    return img


def _blink_frame(i: int) -> Image.Image:
    img, draw = _canvas()
    phase = i % 6
    if phase in (0, 5):
        left, right = _draw_eye_base(draw)
        _draw_pupil(draw, left)
        _draw_pupil(draw, right)
        return img
    if phase in (1, 4):
        draw.rounded_rectangle((36, 130, 104, 150), radius=10, fill=WHITE)
        draw.rounded_rectangle((136, 130, 204, 150), radius=10, fill=WHITE)
        return img
    draw.line((35, 140, 105, 140), fill=WHITE, width=6)
    draw.line((135, 140, 205, 140), fill=WHITE, width=6)
    return img


def _write_sequence(name: str, count: int, out_dir: Path) -> None:
    seq_dir = out_dir / name
    seq_dir.mkdir(parents=True, exist_ok=True)
    for idx in range(count):
        if name == "neutral":
            frame = _neutral_frame(idx)
        elif name == "happy":
            frame = _happy_frame(idx)
        elif name == "blink":
            frame = _blink_frame(idx)
        else:
            raise ValueError(f"unsupported expression: {name}")
        frame.save(seq_dir / f"{idx:03d}.png")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate demo eye expression PNG assets for 240x320 TFT.")
    parser.add_argument("--out-dir", default="/tmp/raspirobot_eyes", help="Output assets root.")
    parser.add_argument("--frames", type=int, default=6, help="Frame count per expression.")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    _write_sequence("neutral", args.frames, out_dir)
    _write_sequence("happy", args.frames, out_dir)
    _write_sequence("blink", args.frames, out_dir)
    print(f"[eyes-assets] generated at: {out_dir}")


if __name__ == "__main__":
    main()
