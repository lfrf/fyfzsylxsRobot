#!/usr/bin/env python3
"""
生成机器人眼睛动画素材。
尺寸：320x240（横放屏幕）
风格：黑底、白色圆形眼白、黑色瞳孔、白色高光点

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
EYEBALL_R = 88    # 眼白半径
PUPIL_R = 54      # 瞳孔半径
HIGHLIGHT_R = 12  # 高光半径


def _draw_eye(
    draw: ImageDraw.ImageDraw,
    cx: int,
    cy: int,
    pupil_dx: int = 0,
    pupil_dy: int = 0,
    blink: float = 0.0,  # 0.0=全开, 1.0=全闭
) -> None:
    """画一只眼睛。blink=0全开，blink=1全闭（变成长条）。"""

    if blink >= 1.0:
        # 全闭：画一个白色圆角矩形长条
        bar_h = 12
        draw.rounded_rectangle(
            [cx - EYEBALL_R, cy - bar_h // 2, cx + EYEBALL_R, cy + bar_h // 2],
            radius=bar_h // 2,
            fill=WHITE,
        )
        return

    if blink > 0.0:
        # 眯眼过渡：眼白高度逐渐压缩成长条
        open_r = EYEBALL_R
        bar_h = 12
        # 当前眼白高度从 open_r*2 线性压缩到 bar_h
        current_h = int(open_r * 2 * (1 - blink) + bar_h * blink)
        half_h = max(current_h // 2, bar_h // 2)

        draw.ellipse(
            [cx - open_r, cy - half_h, cx + open_r, cy + half_h],
            fill=WHITE,
        )

        # 瞳孔也随之压缩
        pupil_h = max(int(PUPIL_R * (1 - blink)), 4)
        px = cx + pupil_dx
        py = cy + pupil_dy
        draw.ellipse(
            [px - PUPIL_R, py - pupil_h, px + PUPIL_R, py + pupil_h],
            fill=BLACK,
        )

        # 高光
        if pupil_h > 8:
            hx = px - PUPIL_R // 3
            hy = py - pupil_h // 2
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


# ── neutral：瞳孔漂移 + 眨眼 ──────────────────────────────

def _neutral_frames() -> list[Image.Image]:
    frames = []
    total = 24

    # 瞳孔漂移轨迹（正弦波）
    drift_x = [int(6 * math.sin(2 * math.pi * i / total)) for i in range(total)]
    drift_y = [int(3 * math.sin(4 * math.pi * i / total)) for i in range(total)]

    # 眨眼在第 16-20 帧
    blink_frames = {16: 0.3, 17: 0.7, 18: 1.0, 19: 0.7, 20: 0.3}

    for i in range(total):
        img, draw = _canvas()
        blink = blink_frames.get(i, 0.0)
        _draw_eye(draw, CX, CY, drift_x[i], drift_y[i], blink)
        frames.append(img)

    return frames


# ── happy：笑眼（弧形） ───────────────────────────────────

def _happy_frames() -> list[Image.Image]:
    frames = []
    for i in range(8):
        img, draw = _canvas()

        # 眼白（上半圆）
        draw.ellipse(
            [CX - EYEBALL_R, CY - EYEBALL_R, CX + EYEBALL_R, CY + EYEBALL_R],
            fill=WHITE,
        )
        # 用黑色遮住下半部分，形成笑眼
        offset = int(10 + 4 * math.sin(2 * math.pi * i / 8))
        draw.rectangle([CX - EYEBALL_R - 5, CY - offset, CX + EYEBALL_R + 5, CY + EYEBALL_R + 5], fill=BLACK)

        # 高光
        draw.ellipse(
            [CX - 30 - HIGHLIGHT_R, CY - 40 - HIGHLIGHT_R,
             CX - 30 + HIGHLIGHT_R, CY - 40 + HIGHLIGHT_R],
            fill=WHITE,
        )
        frames.append(img)

    return frames


# ── comfort：柔和下垂眼 ───────────────────────────────────

def _comfort_frames() -> list[Image.Image]:
    frames = []
    for i in range(8):
        img, draw = _canvas()

        # 眼白
        draw.ellipse(
            [CX - EYEBALL_R, CY - EYEBALL_R + 10, CX + EYEBALL_R, CY + EYEBALL_R + 10],
            fill=WHITE,
        )

        # 瞳孔（稍微偏下）
        dy = 8 + int(2 * math.sin(2 * math.pi * i / 8))
        draw.ellipse(
            [CX - PUPIL_R, CY - PUPIL_R + dy, CX + PUPIL_R, CY + PUPIL_R + dy],
            fill=BLACK,
        )

        # 高光
        draw.ellipse(
            [CX - 20 - HIGHLIGHT_R, CY - 20 - HIGHLIGHT_R + dy,
             CX - 20 + HIGHLIGHT_R, CY - 20 + HIGHLIGHT_R + dy],
            fill=WHITE,
        )

        # 上眼皮稍微下垂
        droop = 18
        draw.ellipse(
            [CX - EYEBALL_R, CY - EYEBALL_R + 10,
             CX + EYEBALL_R, CY - EYEBALL_R + 10 + droop * 2],
            fill=BLACK,
        )

        frames.append(img)

    return frames


# ── listening：睁大眼睛 ───────────────────────────────────

def _listening_frames() -> list[Image.Image]:
    frames = []
    for i in range(8):
        img, draw = _canvas()

        # 眼白（稍大）
        r = EYEBALL_R + 6
        draw.ellipse([CX - r, CY - r, CX + r, CY + r], fill=WHITE)

        # 瞳孔居中，轻微脉动
        pr = PUPIL_R - 4 + int(4 * math.sin(2 * math.pi * i / 8))
        draw.ellipse([CX - pr, CY - pr, CX + pr, CY + pr], fill=BLACK)

        # 高光
        draw.ellipse(
            [CX - 22 - HIGHLIGHT_R, CY - 22 - HIGHLIGHT_R,
             CX - 22 + HIGHLIGHT_R, CY - 22 + HIGHLIGHT_R],
            fill=WHITE,
        )

        frames.append(img)

    return frames


# ── blink：快速眨眼过渡 ───────────────────────────────────

def _blink_frames() -> list[Image.Image]:
    blink_seq = [0.0, 0.4, 0.8, 1.0, 0.8, 0.4]
    frames = []
    for b in blink_seq:
        img, draw = _canvas()
        _draw_eye(draw, CX, CY, 0, 0, b)
        frames.append(img)
    return frames


# ── 写入文件 ──────────────────────────────────────────────

def _save(frames: list[Image.Image], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
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
