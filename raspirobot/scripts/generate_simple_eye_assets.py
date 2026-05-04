#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Callable

from PIL import Image, ImageDraw, ImageFilter

W = 320
H = 240
BG = (0, 0, 0)
WHITE = (250, 250, 250)
BLACK = (0, 0, 0)

CX = W // 2
CY = H // 2

# 单眼素材尺寸与风格参数
EYE_W = 136
EYE_H = 108
EYE_RADIUS = 30
PUPIL_R = 26
HIGHLIGHT_R = 6


def canvas() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (W, H), BG)
    return img, ImageDraw.Draw(img)


def draw_eye(
    draw: ImageDraw.ImageDraw,
    cx: int,
    cy: int,
    *,
    openness: float = 1.0,
    pupil_dx: int = 0,
    pupil_dy: int = 0,
    pupil_r: int = PUPIL_R,
    eye_w: int = EYE_W,
    eye_h: int = EYE_H,
    radius: int = EYE_RADIUS,
    highlight: bool = True,
    brow_shadow: bool = True,
) -> None:
    openness = max(0.18, min(1.0, openness))
    h = max(18, int(eye_h * openness))

    # 单眼应该是一个整体，不是拼成左右两只眼的感觉。
    # 在整体轮廓内部仅做轻微不对称：右侧略更收，左侧略更圆。
    x0 = cx - eye_w // 2
    y0 = cy - h // 2
    x1 = cx + eye_w // 2
    y1 = cy + h // 2

    base_r = min(radius, h // 2, eye_w // 2)
    draw.rounded_rectangle((x0, y0, x1, y1), radius=base_r, fill=WHITE)

    # 轻微的单眼内部偏形：左上更饱满，右侧更收，仍然是一个整体。
    left_bulge = max(4, int(eye_w * 0.11))
    right_trim = max(2, int(eye_w * 0.06))
    top_bulge = max(2, int(h * 0.04))
    bottom_trim = max(2, int(h * 0.03))
    draw.ellipse((x0 - 2, y0 + 2, x0 + left_bulge * 2, y1 - bottom_trim), fill=WHITE)
    draw.ellipse((x1 - right_trim * 2 - 6, y0 + 5, x1 + 2, y1 - 4), fill=WHITE)
    draw.rectangle((x0 + left_bulge, y0 + 1, x1 - right_trim, y1 - 1), fill=WHITE)
    draw.rectangle((x0 + left_bulge, y0, x1 - right_trim, y0 + top_bulge + 3), fill=WHITE)
    draw.rectangle((x0 + left_bulge, y1 - top_bulge - 3, x1 - right_trim, y1), fill=WHITE)

    px = cx + pupil_dx
    py = cy + pupil_dy
    pupil_half_h = max(6, int(pupil_r * min(1.0, openness + 0.08)))
    draw.ellipse((px - pupil_r, py - pupil_half_h, px + pupil_r, py + pupil_half_h), fill=BLACK)

    if highlight and openness > 0.55:
        hx = px - pupil_r // 3
        hy = py - pupil_half_h // 3
        draw.ellipse((hx - HIGHLIGHT_R, hy - HIGHLIGHT_R, hx + HIGHLIGHT_R, hy + HIGHLIGHT_R), fill=WHITE)

    if brow_shadow:
        # 轻微上方压感，让基础状态更完整，但不画成明显眉毛
        shadow_h = max(4, int(eye_h * 0.12))
        shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        sdraw = ImageDraw.Draw(shadow)
        sdraw.rounded_rectangle(
            (x0 + 8, y0 - shadow_h - 6, x1 - 8, y0 - 4),
            radius=max(2, shadow_h // 2),
            fill=(28, 28, 28, 150),
        )
        shadow = shadow.filter(ImageFilter.GaussianBlur(radius=1.2))
        draw.bitmap((0, 0), shadow, fill=None)


def compose_frame(
    left_cfg: dict,
    right_cfg: dict,
) -> Image.Image:
    img, draw = canvas()
    draw_eye(draw, CX - 52, CY, **left_cfg)
    draw_eye(draw, CX + 52, CY, **right_cfg)
    return img


def frames_neutral(count: int, eye_shift: int = 1) -> list[Image.Image]:
    frames: list[Image.Image] = []
    # 待机帧节奏更长、更缓，并加入极轻微的高光/上沿变化，形成“呼吸感”。
    # 变化仍然限制在 1~2 像素，避免像乱晃。
    offsets = [
        (0, 0, 0, 0),
        (0, 0, 0, 0),
        (eye_shift, 0, 0, 0),
        (0, 0, 1, 0),
        (-eye_shift, 0, 0, 0),
        (0, 1, 0, 1),
        (0, 0, 0, 0),
        (0, 0, 1, 1),
        (-eye_shift, 1, 0, 0),
        (0, 0, 0, 0),
    ]
    for i in range(count):
        dx, dy, l_hi, r_hi = offsets[i % len(offsets)]
        frame = compose_frame(
            {"pupil_dx": dx, "pupil_dy": dy, "openness": 1.0, "pupil_r": 26 + l_hi, "highlight": True},
            {"pupil_dx": dx, "pupil_dy": dy, "openness": 1.0, "pupil_r": 26 + r_hi, "highlight": True},
        )
        frames.append(frame)
    return frames


def frames_blink(count: int) -> list[Image.Image]:
    frames: list[Image.Image] = []
    seq = [1.0, 0.72, 0.35, 0.12, 0.35, 0.72]
    for i in range(count):
        o = seq[i % len(seq)]
        frame = compose_frame(
            {"openness": o, "pupil_dx": 0, "pupil_dy": 0, "highlight": o > 0.6},
            {"openness": o, "pupil_dx": 0, "pupil_dy": 0, "highlight": o > 0.6},
        )
        frames.append(frame)
    return frames


def frames_happy(count: int) -> list[Image.Image]:
    frames: list[Image.Image] = []
    offsets = [(0, 0), (1, 0), (0, -1), (-1, 0), (0, 0), (1, 1)]
    for i in range(count):
        dx, dy = offsets[i % len(offsets)]
        frame = compose_frame(
            {"openness": 0.94, "pupil_dx": dx, "pupil_dy": dy - 1, "pupil_r": 24},
            {"openness": 0.94, "pupil_dx": dx + 1, "pupil_dy": dy - 1, "pupil_r": 24},
        )
        frames.append(frame)
    return frames


def frames_listening(count: int) -> list[Image.Image]:
    frames: list[Image.Image] = []
    offsets = [(0, -1), (1, -1), (0, 0), (-1, -1), (0, -1), (1, 0)]
    for i in range(count):
        dx, dy = offsets[i % len(offsets)]
        frame = compose_frame(
            {"openness": 1.0, "pupil_dx": dx, "pupil_dy": dy, "pupil_r": 24},
            {"openness": 0.98, "pupil_dx": dx + 1, "pupil_dy": dy, "pupil_r": 24},
        )
        frames.append(frame)
    return frames


def frames_thinking(count: int) -> list[Image.Image]:
    frames: list[Image.Image] = []
    offsets = [(6, -3), (7, -3), (6, -2), (5, -3), (6, -3), (5, -2)]
    for i in range(count):
        dx, dy = offsets[i % len(offsets)]
        frame = compose_frame(
            {"openness": 0.92, "pupil_dx": dx, "pupil_dy": dy, "pupil_r": 24},
            {"openness": 0.90, "pupil_dx": dx - 2, "pupil_dy": dy + 1, "pupil_r": 24},
        )
        frames.append(frame)
    return frames


def frames_comfort(count: int) -> list[Image.Image]:
    frames: list[Image.Image] = []
    offsets = [(0, 1), (1, 1), (0, 0), (-1, 0), (0, 1), (1, 0)]
    for i in range(count):
        dx, dy = offsets[i % len(offsets)]
        frame = compose_frame(
            {"openness": 0.80, "pupil_dx": dx, "pupil_dy": dy, "pupil_r": 24},
            {"openness": 0.82, "pupil_dx": dx + 1, "pupil_dy": dy, "pupil_r": 24},
        )
        frames.append(frame)
    return frames


def frames_sleep(count: int) -> list[Image.Image]:
    frames: list[Image.Image] = []
    seq = [0.25, 0.22, 0.20, 0.22]
    for i in range(count):
        o = seq[i % len(seq)]
        img = Image.new("RGB", (W, H), BG)
        draw = ImageDraw.Draw(img)
        # 只画闭眼弧线，几乎不动
        for xoff in (-52, 52):
            cx = CX + xoff
            cy = CY + 6
            bbox = (cx - 54, cy - 18, cx + 54, cy + 18)
            draw.arc(bbox, start=18, end=162, fill=WHITE, width=max(12, int(18 * o)))
        frames.append(img)
    return frames


EXPRESSION_BUILDERS: dict[str, Callable[[int], list[Image.Image]]] = {
    "neutral": frames_neutral,
    "blink": frames_blink,
    "happy": frames_happy,
    "listening": frames_listening,
    "thinking": frames_thinking,
    "comfort": frames_comfort,
    "sleep": frames_sleep,
}


def save_frames(frames: list[Image.Image], out_dir: Path, expression: str, side: str) -> None:
    target = out_dir / side / expression
    target.mkdir(parents=True, exist_ok=True)
    for old in target.glob("*.png"):
        old.unlink()
    for i, frame in enumerate(frames):
        frame.save(target / f"{i:03d}.png")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate simple robot eye assets for left/right eyes.")
    parser.add_argument("--out-dir", default="raspirobot/assets/eyes", help="Output root directory.")
    parser.add_argument("--frames", type=int, default=6, help="Frame count per expression.")
    parser.add_argument(
        "--expressions",
        default="neutral,blink,happy,listening,thinking,comfort,sleep",
        help="Comma-separated expression names.",
    )
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    expressions = [x.strip() for x in args.expressions.split(",") if x.strip()]

    for expr in expressions:
        builder = EXPRESSION_BUILDERS.get(expr)
        if builder is None:
            raise ValueError(f"unsupported expression: {expr}")
        frames = builder(args.frames)
        save_frames(frames, out_dir, expr, "left")
        save_frames(frames, out_dir, expr, "right")
        print(f"generated {expr}: {len(frames)} frames -> {out_dir / 'left' / expr}")


if __name__ == "__main__":
    main()
