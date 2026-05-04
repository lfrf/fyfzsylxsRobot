#!/usr/bin/env python3
"""
生成机器人单眼动画素材。
尺寸：320x240（横放屏幕）
风格：参考 demo 素材，使用更小变化区域和更简单线条，降低双屏单眼显示时的撕裂感。

用法：
    python -m raspirobot.scripts.generate_eye_assets
    python -m raspirobot.scripts.generate_eye_assets --out-dir raspirobot/assets/eyes
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

W = 320
H = 240
BG = (0, 0, 0)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)

# 眼睛中心
CX = W // 2
CY = H // 2

# 尺寸参数
# 圆角方眼风格：黑底、白色圆角眼白、黑色瞳孔，和参考图保持一致。
EYE_W = 138
EYE_H = 110
EYE_RADIUS = 32
PUPIL_R = 28
HIGHLIGHT_R = 7


def _draw_eye(
    draw: ImageDraw.ImageDraw,
    cx: int,
    cy: int,
    pupil_dx: int = 0,
    pupil_dy: int = 0,
    openness: float = 1.0,
    pupil_r: int = PUPIL_R,
    eye_w: int = EYE_W,
    eye_h: int = EYE_H,
    radius: int = EYE_RADIUS,
    highlight: bool = False,
) -> None:
    """画一只圆角方眼。

    openness=1.0 表示全开；数值越小，眼睛越微闭。
    """
    openness = max(0.18, min(1.0, openness))
    h = max(18, int(eye_h * openness))
    r = min(radius, h // 2, eye_w // 2)
    draw.rounded_rectangle(
        [cx - eye_w // 2, cy - h // 2, cx + eye_w // 2, cy + h // 2],
        radius=r,
        fill=WHITE,
    )

    px = cx + pupil_dx
    py = cy + pupil_dy
    pupil_half_h = max(6, int(pupil_r * min(1.0, openness + 0.08)))
    draw.ellipse(
        [px - pupil_r, py - pupil_half_h, px + pupil_r, py + pupil_half_h],
        fill=BLACK,
    )

    if highlight and openness > 0.65:
        hx = px - pupil_r // 3
        hy = py - pupil_half_h // 3
        draw.ellipse(
            [hx - HIGHLIGHT_R, hy - HIGHLIGHT_R, hx + HIGHLIGHT_R, hy + HIGHLIGHT_R],
            fill=WHITE,
        )


def _canvas() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (W, H), BG)
    return img, ImageDraw.Draw(img)


# ── neutral：圆角方眼待机 ────────────────────────────────

def _neutral_frames() -> list[Image.Image]:
    frames = []
    offsets = [(-1, 0), (0, 0), (1, 0), (1, 1), (0, 0), (-1, 1)]
    for dx, dy in offsets:
        img, draw = _canvas()
        _draw_eye(draw, CX, CY, dx, dy, openness=1.0, pupil_r=28)
        frames.append(img)

    return frames


# ── happy：圆角方眼 + 微笑弧形瞳孔 ───────────────────────

def _draw_smile_pupil(draw: ImageDraw.ImageDraw, cx: int, cy: int, width: int = 56, height: int = 30, thickness: int = 10) -> None:
    bbox = [cx - width // 2, cy - height // 2, cx + width // 2, cy + height // 2]
    draw.arc(bbox, start=200, end=340, fill=BLACK, width=thickness)


def _happy_frames() -> list[Image.Image]:
    frames = []
    for dy in (0, 1, 0, -1):
        img, draw = _canvas()
        _draw_eye(draw, CX, CY, 0, dy, openness=0.92, pupil_r=26)
        _draw_smile_pupil(draw, CX, CY + 10 + dy)
        frames.append(img)

    return frames


# ── comfort：微闭并下移的温柔眼 ───────────────────────────

def _comfort_frames() -> list[Image.Image]:
    frames = []
    offsets = [(0, 1), (1, 1), (1, 0), (0, 1), (-1, 0), (-1, 1)]
    for dx, dy in offsets:
        img, draw = _canvas()
        _draw_eye(draw, CX, CY + 6, dx, dy, openness=0.78, pupil_r=26)
        frames.append(img)

    return frames


# ── listening：更打开、更专注的圆角方眼 ───────────────────

def _listening_frames() -> list[Image.Image]:
    frames = []
    offsets = [(0, -1), (0, -2), (1, -1), (0, -1), (-1, -1), (0, 0)]
    for dx, dy in offsets:
        img, draw = _canvas()
        _draw_eye(draw, CX, CY - 3, dx, dy, openness=1.0, pupil_r=24, eye_w=142, eye_h=116)
        frames.append(img)

    return frames


# ── thinking：圆角方眼 + 偏视瞳孔 ─────────────────────────

def _thinking_frames() -> list[Image.Image]:
    frames = []
    offsets = [(6, -4), (7, -4), (6, -3), (5, -4)]
    for dx, dy in offsets:
        img, draw = _canvas()
        _draw_eye(draw, CX, CY, dx, dy, openness=0.92, pupil_r=24)
        frames.append(img)

    return frames


# ── sleep：圆润 U 形闭眼，几乎静止 ────────────────────────

def _sleep_frames() -> list[Image.Image]:
    frames = []
    for dy in (0, 1):
        img, draw = _canvas()
        _draw_closed_smile_arc(img, CX, CY + 8 + dy, width=118, height=64, thickness=18)
        frames.append(img)

    return frames


# ── blink：圆角方眼直接切换到 U 形闭眼 ────────────────────

def _draw_closed_smile_arc(img: Image.Image, cx: int, cy: int, width: int = 120, height: int = 64, thickness: int = 22) -> None:
    """画 U 形闭眼弧线，用作眨眼闭合状态。"""
    scale = 4
    layer = Image.new("RGBA", (W * scale, H * scale), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    bbox = [
        (cx - width // 2) * scale,
        (cy - height // 2) * scale,
        (cx + width // 2) * scale,
        (cy + height // 2) * scale,
    ]
    draw.arc(
        bbox,
        start=18,
        end=162,
        fill=WHITE + (255,),
        width=thickness * scale,
    )
    layer = layer.filter(ImageFilter.GaussianBlur(radius=0.25 * scale))
    layer = layer.resize((W, H), Image.Resampling.LANCZOS)
    img.paste(Image.new("RGB", (W, H), BG), mask=Image.new("L", (W, H), 0))
    img.paste(Image.new("RGB", (W, H), WHITE), mask=layer.getchannel("A"))


def _blink_frames() -> list[Image.Image]:
    # 直接从圆角方眼切换到 U 形闭眼，不再使用粗白条过渡。
    frames = []

    img, draw = _canvas()
    _draw_eye(draw, CX, CY, 0, 0, openness=1.0, pupil_r=28)
    frames.append(img)

    img, draw = _canvas()
    _draw_closed_smile_arc(img, CX, CY + 8, width=118, height=64, thickness=18)
    frames.append(img)

    img, draw = _canvas()
    _draw_closed_smile_arc(img, CX, CY + 8, width=118, height=64, thickness=18)
    frames.append(img)

    img, draw = _canvas()
    _draw_eye(draw, CX, CY, 0, 0, openness=1.0, pupil_r=28)
    frames.append(img)

    return frames


# ── 写入文件 ──────────────────────────────────────────────

def _save(frames: list[Image.Image], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    # 重新生成素材前清理旧图片，避免旧帧残留被驱动继续加载。
    for old_file in out_dir.iterdir():
        if old_file.is_file() and old_file.suffix.lower() in {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".gif"}:
            old_file.unlink()

    for i, frame in enumerate(frames):
        frame.save(out_dir / f"{i:03d}.png")
    print(f"  生成 {len(frames)} 帧 → {out_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(description="生成机器人眼睛动画素材")
    parser.add_argument(
        "--out-dir",
        default="raspirobot/assets/eyes",
        help="输出根目录，左眼放 left/，右眼放 right/",
    )
    parser.add_argument(
        "--include-happy",
        action="store_true",
        help="同时生成 happy。默认跳过 happy，避免覆盖手工绘制的开心表情素材。",
    )
    args = parser.parse_args()

    root = Path(args.out_dir)

    expressions = {
        "neutral": _neutral_frames,
        "comfort": _comfort_frames,
        "listening": _listening_frames,
        "thinking": _thinking_frames,
        "sleep": _sleep_frames,
        "blink": _blink_frames,
    }
    if args.include_happy:
        expressions["happy"] = _happy_frames

    for name, fn in expressions.items():
        print(f"生成 {name}...")
        frames = fn()
        _save(frames, root / "left" / name)
        _save(frames, root / "right" / name)

    print("\n完成！所有素材已生成到:", root)


if __name__ == "__main__":
    main()
