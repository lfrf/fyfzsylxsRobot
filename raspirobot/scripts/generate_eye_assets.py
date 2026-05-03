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

from PIL import Image, ImageDraw

W = 320
H = 240
BG = (0, 0, 0)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)

# 眼睛中心
CX = W // 2
CY = H // 2

# 尺寸参数
# 参考 demo 素材：缩小眼睛主体和瞳孔，减少每帧大面积黑白翻转。
EYEBALL_R = 62    # 眼白半径
PUPIL_R = 24      # 瞳孔半径
HIGHLIGHT_R = 7   # 高光半径


def _draw_eye(
    draw: ImageDraw.ImageDraw,
    cx: int,
    cy: int,
    pupil_dx: int = 0,
    pupil_dy: int = 0,
    blink: float = 0.0,  # 0.0=全开, 1.0=全闭
) -> None:
    """画一只眼睛。
    blink=0: 全开
    blink=0.5: 半闭（椭圆压扁到一半高度）
    blink=1.0: 全闭（白色圆角矩形长条）
    """
    BAR_H = 14  # 闭眼长条高度，越小变化区域越小

    if blink >= 1.0:
        # 全闭：白色圆角矩形长条
        draw.rounded_rectangle(
            [cx - EYEBALL_R, cy - BAR_H // 2, cx + EYEBALL_R, cy + BAR_H // 2],
            radius=BAR_H // 2,
            fill=WHITE,
        )
        return

    if blink > 0.0:
        # 过渡：眼白高度从 EYEBALL_R 线性压缩到 BAR_H//2
        half_h = int(EYEBALL_R * (1 - blink) + (BAR_H // 2) * blink)
        half_h = max(half_h, BAR_H // 2)

        draw.ellipse(
            [cx - EYEBALL_R, cy - half_h, cx + EYEBALL_R, cy + half_h],
            fill=WHITE,
        )

        # 瞳孔随之压缩
        pupil_half_h = max(int(PUPIL_R * (1 - blink)), BAR_H // 2 - 2)
        px = cx + pupil_dx
        py = cy + pupil_dy
        draw.ellipse(
            [px - PUPIL_R, py - pupil_half_h, px + PUPIL_R, py + pupil_half_h],
            fill=BLACK,
        )

        # 高光（压扁时隐藏）
        if blink < 0.4:
            hx = px - PUPIL_R // 3
            hy = py - pupil_half_h // 2
            draw.ellipse(
                [hx - HIGHLIGHT_R, hy - HIGHLIGHT_R, hx + HIGHLIGHT_R, hy + HIGHLIGHT_R],
                fill=WHITE,
            )
        return

    # 全开
    draw.ellipse(
        [cx - EYEBALL_R, cy - EYEBALL_R, cx + EYEBALL_R, cy + EYEBALL_R],
        fill=WHITE,
    )

    px = cx + pupil_dx
    py = cy + pupil_dy
    draw.ellipse(
        [px - PUPIL_R, py - PUPIL_R, px + PUPIL_R, py + PUPIL_R],
        fill=BLACK,
    )

    hx = px - PUPIL_R // 3
    hy = py - PUPIL_R // 3
    draw.ellipse(
        [hx - HIGHLIGHT_R, hy - HIGHLIGHT_R, hx + HIGHLIGHT_R, hy + HIGHLIGHT_R],
        fill=WHITE,
    )


def _canvas() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (W, H), BG)
    return img, ImageDraw.Draw(img)


# ── neutral：demo 风格低变化待机 ──────────────────────────

def _neutral_frames() -> list[Image.Image]:
    frames = []
    offsets = [(-1, 0), (0, 0), (1, 0), (0, 1), (0, 0), (0, -1)]

    # 多数时间近似静态，只保留极小幅度的瞳孔漂移。
    for dx, dy in offsets:
        img, draw = _canvas()
        _draw_eye(draw, CX, CY, dx, dy, 0.0)
        frames.append(img)

    return frames


# ── happy：笑眼（弧形） ───────────────────────────────────

def _draw_crescent(img: Image.Image, cx: int, cy: int, dy: int = 0) -> None:
    """画更饱满、更自然的笑眼弧线。"""
    draw = ImageDraw.Draw(img)

    # 用更大的弧度和更厚的笔触，避免端点额外补圆造成的突兀感。
    arc_width = 20
    arc_box = (cx - 88, cy - 36 + dy, cx + 88, cy + 64 + dy)
    draw.arc(arc_box, start=202, end=338, fill=WHITE, width=arc_width)


def _happy_frames() -> list[Image.Image]:
    frames = []
    total = 6
    for i in range(total):
        img, draw = _canvas()

        # demo 风格：小幅弧线变化
        dy = [0, 1, 0, -1, 0, 1][i]
        _draw_crescent(img, CX, CY, dy)

        frames.append(img)

    return frames


# ── comfort：柔和下垂眼 ───────────────────────────────────

def _comfort_frames() -> list[Image.Image]:
    frames = []
    offsets = [(0, 2), (0, 2), (1, 2), (0, 3), (-1, 2), (0, 2)]
    for dx, dy in offsets:
        img, draw = _canvas()
        _draw_eye(draw, CX, CY + 6, dx, dy, 0.18)
        frames.append(img)

    return frames


# ── listening：睁大眼睛 ───────────────────────────────────

def _listening_frames() -> list[Image.Image]:
    frames = []
    offsets = [(0, 0), (0, -1), (1, 0), (0, 0), (-1, 0), (0, 1)]
    for dx, dy in offsets:
        img, draw = _canvas()
        _draw_eye(draw, CX, CY - 2, dx, dy, 0.0)
        frames.append(img)

    return frames


# ── thinking：轻微偏视，表达思考 ──────────────────────────

def _thinking_frames() -> list[Image.Image]:
    frames = []
    offsets = [(4, -3), (5, -3), (4, -2), (3, -3)]
    for dx, dy in offsets:
        img, draw = _canvas()
        _draw_eye(draw, CX, CY, dx, dy, 0.0)
        frames.append(img)

    return frames


# ── sleep：闭眼休眠，几乎静止 ────────────────────────────

def _sleep_frames() -> list[Image.Image]:
    frames = []
    for dy in (0, 1):
        img, draw = _canvas()
        _draw_closed_line(draw, CX, CY + dy, width=96, thickness=6)
        frames.append(img)

    return frames


# ── blink：demo 风格线条式眨眼 ────────────────────────────

def _draw_closed_bar(draw: ImageDraw.ImageDraw, cx: int, cy: int, width: int, height: int) -> None:
    draw.rounded_rectangle(
        [cx - width // 2, cy - height // 2, cx + width // 2, cy + height // 2],
        radius=max(1, height // 2),
        fill=WHITE,
    )


def _draw_closed_line(draw: ImageDraw.ImageDraw, cx: int, cy: int, width: int, thickness: int) -> None:
    draw.line(
        [cx - width // 2, cy, cx + width // 2, cy],
        fill=WHITE,
        width=thickness,
    )


def _blink_frames() -> list[Image.Image]:
    # 符号化线条眨眼：避免整只眼睛从圆形大面积压缩，降低眨眼瞬间撕裂感。
    frames = []

    img, draw = _canvas()
    _draw_eye(draw, CX, CY, 0, 0, 0.0)
    frames.append(img)

    img, draw = _canvas()
    _draw_closed_bar(draw, CX, CY, width=118, height=28)
    frames.append(img)

    img, draw = _canvas()
    _draw_closed_line(draw, CX, CY, width=110, thickness=8)
    frames.append(img)

    img, draw = _canvas()
    _draw_closed_bar(draw, CX, CY, width=118, height=28)
    frames.append(img)

    img, draw = _canvas()
    _draw_eye(draw, CX, CY, 0, 0, 0.0)
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
    args = parser.parse_args()

    root = Path(args.out_dir)

    expressions = {
        "neutral": _neutral_frames,
        "happy": _happy_frames,
        "comfort": _comfort_frames,
        "listening": _listening_frames,
        "thinking": _thinking_frames,
        "sleep": _sleep_frames,
        "blink": _blink_frames,
    }

    for name, fn in expressions.items():
        print(f"生成 {name}...")
        frames = fn()
        _save(frames, root / "left" / name)
        _save(frames, root / "right" / name)

    print("\n完成！所有素材已生成到:", root)


if __name__ == "__main__":
    main()
