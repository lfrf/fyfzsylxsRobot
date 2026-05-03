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
    """画一只眼睛。
    blink=0: 全开
    blink=0.5: 半闭（椭圆压扁到一半高度）
    blink=1.0: 全闭（白色圆角矩形长条）
    """
    BAR_H = 24  # 长条高度

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


# ── neutral：缓慢瞳孔漂移 + 轻柔眨眼 ───────────────────────

def _neutral_frames() -> list[Image.Image]:
    frames = []
    total = 32

    # 陪伴型机器人更适合慢一点、幅度小一点的漂移
    drift_x = [int(4 * math.sin(2 * math.pi * i / total)) for i in range(total)]
    drift_y = [int(2 * math.sin(2 * math.pi * i / total)) for i in range(total)]

    # 眨眼改成更轻柔的半闭 → 全闭 → 半闭，减少大幅跳变
    blink_frames = {
        22: 0.45,
        23: 1.0,
        24: 1.0,
        25: 0.45,
    }

    for i in range(total):
        img, draw = _canvas()
        blink = blink_frames.get(i, 0.0)
        _draw_eye(draw, CX, CY, drift_x[i], drift_y[i], blink)
        frames.append(img)

    return frames


# ── happy：笑眼（弧形） ───────────────────────────────────

def _draw_crescent(img: Image.Image, cx: int, cy: int, dy: int = 0) -> None:
    """用 numpy 逐像素绘制月牙形，两尖朝下，开口向下。"""
    import numpy as np

    arr = np.array(img)
    h, w = arr.shape[:2]

    # 外椭圆参数（月牙外轮廓）
    rx_out = 95   # 水平半径
    ry_out = 52   # 垂直半径

    # 内椭圆参数（挖去上半部分）
    rx_in = 88
    ry_in = 38
    # 内椭圆向上偏移，控制月牙厚度
    inner_offset_y = -28

    ys, xs = np.ogrid[:h, :w]

    # 外椭圆区域
    outer = ((xs - cx) ** 2 / rx_out ** 2 + (ys - (cy + dy)) ** 2 / ry_out ** 2) <= 1

    # 内椭圆区域（向上偏移，挖去上部）
    inner = ((xs - cx) ** 2 / rx_in ** 2 + (ys - (cy + dy + inner_offset_y)) ** 2 / ry_in ** 2) <= 1

    # 月牙 = 外椭圆 - 内椭圆
    crescent = outer & ~inner

    arr[crescent] = [255, 255, 255]
    img.paste(Image.fromarray(arr))


def _happy_frames() -> list[Image.Image]:
    frames = []
    total = 16
    for i in range(total):
        img, draw = _canvas()

        # 可爱陪伴型笑眼：更慢、更小幅的上下浮动
        dy = int(2 * math.sin(2 * math.pi * i / total))
        _draw_crescent(img, CX, CY, dy)

        frames.append(img)

    return frames


# ── comfort：柔和下垂眼 ───────────────────────────────────

def _comfort_frames() -> list[Image.Image]:
    frames = []
    total = 16
    for i in range(total):
        img, draw = _canvas()

        # 眼白
        draw.ellipse(
            [CX - EYEBALL_R, CY - EYEBALL_R + 10, CX + EYEBALL_R, CY + EYEBALL_R + 10],
            fill=WHITE,
        )

        # 瞳孔（稍微偏下，慢速呼吸感）
        dy = 8 + int(1 * math.sin(2 * math.pi * i / total))
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
    total = 16
    for i in range(total):
        img, draw = _canvas()

        # 眼白（稍大）
        r = EYEBALL_R + 6
        draw.ellipse([CX - r, CY - r, CX + r, CY + r], fill=WHITE)

        # 瞳孔居中，轻微慢速脉动，避免快速放大缩小造成撕裂感
        pr = PUPIL_R - 4 + int(2 * math.sin(2 * math.pi * i / total))
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
    # 慢速柔和眨眼：减少睁开/闭合之间的大面积瞬间跳变
    blink_seq = [0.0, 0.35, 0.75, 1.0, 1.0, 0.75, 0.35, 0.0]
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
