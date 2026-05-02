#!/usr/bin/env python3
"""
ST7789 屏幕独立测试脚本
完全不依赖项目任何模块，直接操作 st7789 包。

三个阶段：
  阶段一：纯色填充（验证 SPI 通信）
  阶段二：加载项目素材（验证图片渲染）
  阶段三：ST7789EyesDriver 表情切换（验证渲染线程）

用法：
  cd /home/pi/Desktop/code/fyfzsylxsRobot
  source .venv/bin/activate
  python scripts/test_st7789_raw.py

可选参数：
  --width       屏幕宽度，默认 240
  --height      屏幕高度，默认 320
  --dc          DC GPIO，默认 25
  --rst         RST GPIO，默认 24
  --cs          CS 片选，默认 0（CE0）
  --spi-port    SPI 端口，默认 0
  --spi-speed   SPI 速度，默认 4000000（4MHz，比默认低，更稳定）
  --assets-dir  素材目录，默认 raspirobot/assets/eyes
  --stage       只运行指定阶段 1/2/3，默认全部运行
"""

from __future__ import annotations

import argparse
import sys
import time
import traceback
from pathlib import Path


# ─────────────────────────────────────────────
# 工具函数
# ─────────────────────────────────────────────

def ok(msg: str) -> None:
    print(f"  [OK] {msg}")


def fail(msg: str) -> None:
    print(f"  [FAIL] {msg}")


def info(msg: str) -> None:
    print(f"  {msg}")


def section(title: str) -> None:
    print()
    print(f"{'='*50}")
    print(f"  {title}")
    print(f"{'='*50}")


# ─────────────────────────────────────────────
# 阶段一：纯色填充
# ─────────────────────────────────────────────

def stage1_solid_color(args: argparse.Namespace) -> bool:
    section("阶段一：纯色填充（验证 SPI 通信）")
    info("不依赖任何项目代码，直接调用 st7789 包")

    try:
        import st7789
        ok(f"st7789 包导入成功: {st7789.__file__}")
    except ImportError as e:
        fail(f"st7789 包未安装: {e}")
        info("请运行: pip install st7789")
        return False

    try:
        from PIL import Image
        ok("Pillow 导入成功")
    except ImportError as e:
        fail(f"Pillow 未安装: {e}")
        info("请运行: pip install Pillow")
        return False

    info(f"初始化屏幕: SPI{args.spi_port}, CS={args.cs}, DC={args.dc}, RST={args.rst}, "
         f"{args.width}x{args.height}, {args.spi_speed}Hz")

    try:
        disp = st7789.ST7789(
            args.spi_port,
            args.cs,
            args.dc,
            rst=args.rst,
            width=args.width,
            height=args.height,
            rotation=0,
            spi_speed_hz=args.spi_speed,
        )
        ok("屏幕初始化成功")
    except Exception as e:
        fail(f"屏幕初始化失败: {e}")
        traceback.print_exc()
        return False

    colors = [
        ("红色", (255, 0, 0)),
        ("绿色", (0, 255, 0)),
        ("蓝色", (0, 0, 255)),
        ("白色", (255, 255, 255)),
        ("黑色", (0, 0, 0)),
    ]

    for name, rgb in colors:
        try:
            img = Image.new("RGB", (args.width, args.height), rgb)
            disp.display(img)
            info(f"显示{name} {rgb} ...")
            time.sleep(1.0)
            ok(f"{name} 显示完成")
        except Exception as e:
            fail(f"显示{name}失败: {e}")
            traceback.print_exc()
            return False

    ok("阶段一完成 — 如果屏幕显示了颜色变化，SPI 通信正常")
    return True


# ─────────────────────────────────────────────
# 阶段二：加载项目素材
# ─────────────────────────────────────────────

def stage2_load_assets(args: argparse.Namespace) -> bool:
    section("阶段二：加载项目素材（验证图片渲染）")

    try:
        import st7789
        from PIL import Image, ImageOps
    except ImportError as e:
        fail(f"依赖未安装: {e}")
        return False

    assets_dir = Path(args.assets_dir)
    neutral_dir = assets_dir / "neutral"

    info(f"素材目录: {assets_dir}")

    if not neutral_dir.exists():
        fail(f"neutral 目录不存在: {neutral_dir}")
        info("请确认 ROBOT_EYES_ASSETS_DIR 路径正确")
        return False

    png_files = sorted(neutral_dir.glob("*.png"))
    if not png_files:
        fail(f"neutral 目录下没有 PNG 文件: {neutral_dir}")
        return False

    ok(f"找到 {len(png_files)} 个素材帧: {[f.name for f in png_files]}")

    try:
        disp = st7789.ST7789(
            args.spi_port,
            args.cs,
            args.dc,
            rst=args.rst,
            width=args.width,
            height=args.height,
            rotation=0,
            spi_speed_hz=args.spi_speed,
        )
    except Exception as e:
        fail(f"屏幕初始化失败: {e}")
        traceback.print_exc()
        return False

    for png_path in png_files:
        try:
            with Image.open(png_path) as raw:
                img = raw.convert("RGB")
            info(f"原始尺寸: {img.size}, 缩放到 {args.width}x{args.height}")
            img = ImageOps.fit(img, (args.width, args.height), method=Image.Resampling.BICUBIC)
            disp.display(img)
            ok(f"显示 {png_path.name}")
            time.sleep(0.5)
        except Exception as e:
            fail(f"显示 {png_path.name} 失败: {e}")
            traceback.print_exc()
            return False

    ok("阶段二完成 — 如果屏幕显示了眼睛图案，素材渲染正常")
    return True


# ─────────────────────────────────────────────
# 阶段三：ST7789EyesDriver 表情切换
# ─────────────────────────────────────────────

def stage3_eyes_driver(args: argparse.Namespace) -> bool:
    section("阶段三：ST7789EyesDriver 表情切换（验证渲染线程）")
    info("使用项目的 ST7789EyesDriver 类，验证后台渲染线程")

    # 把项目根目录加入 sys.path
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    info(f"项目根目录: {project_root}")

    try:
        from raspirobot.hardware.st7789_eyes import ST7789EyeConfig, ST7789EyesDriver
        ok("ST7789EyesDriver 导入成功")
    except ImportError as e:
        fail(f"导入失败: {e}")
        traceback.print_exc()
        return False

    try:
        config = ST7789EyeConfig(
            assets_dir=Path(args.assets_dir),
            fps=12,
            width=args.width,
            height=args.height,
            rotation=0,
            spi_port=args.spi_port,
            spi_speed_hz=args.spi_speed,
            dc_gpio=args.dc,
            rst_gpio=args.rst,
            left_cs=args.cs,
            right_cs=1,
            right_enabled=False,
            mirror_right=False,
        )
        driver = ST7789EyesDriver(config)
        ok("ST7789EyesDriver 初始化成功，渲染线程已启动")
    except Exception as e:
        fail(f"ST7789EyesDriver 初始化失败: {e}")
        traceback.print_exc()
        return False

    expressions = ["neutral"]
    for expr in expressions:
        info(f"切换表情: {expr}，持续 3 秒 ...")
        try:
            driver.set_expression(expr)
            time.sleep(3.0)
            ok(f"表情 {expr} 显示完成")
        except Exception as e:
            fail(f"set_expression({expr}) 失败: {e}")
            traceback.print_exc()
            driver.close()
            return False

    driver.close()
    ok("阶段三完成 — 渲染线程正常工作")
    return True


# ─────────────────────────────────────────────
# 主入口
# ─────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="ST7789 屏幕独立测试脚本")
    parser.add_argument("--width", type=int, default=240)
    parser.add_argument("--height", type=int, default=320)
    parser.add_argument("--dc", type=int, default=25)
    parser.add_argument("--rst", type=int, default=24)
    parser.add_argument("--cs", type=int, default=0)
    parser.add_argument("--spi-port", type=int, default=0)
    parser.add_argument("--spi-speed", type=int, default=4_000_000,
                        help="SPI 速度 Hz，默认 4MHz（比 40MHz 更稳定，适合排查问题）")
    parser.add_argument("--assets-dir",
                        default=str(Path(__file__).resolve().parents[1] / "raspirobot/assets/eyes"))
    parser.add_argument("--stage", type=int, choices=[1, 2, 3], default=None,
                        help="只运行指定阶段，默认全部运行")
    args = parser.parse_args()

    print()
    print("ST7789 屏幕独立测试")
    print(f"  屏幕: {args.width}x{args.height}")
    print(f"  SPI: port={args.spi_port}, speed={args.spi_speed}Hz")
    print(f"  GPIO: DC={args.dc}, RST={args.rst}, CS={args.cs}")
    print(f"  素材: {args.assets_dir}")

    results: dict[int, bool] = {}

    if args.stage is None or args.stage == 1:
        results[1] = stage1_solid_color(args)

    if args.stage is None or args.stage == 2:
        results[2] = stage2_load_assets(args)

    if args.stage is None or args.stage == 3:
        results[3] = stage3_eyes_driver(args)

    section("测试结果汇总")
    all_passed = True
    for stage_num, passed in results.items():
        status = "PASS" if passed else "FAIL"
        print(f"  阶段{stage_num}: {status}")
        if not passed:
            all_passed = False

    print()
    if all_passed:
        print("全部通过，屏幕工作正常。")
    else:
        print("有阶段失败，请根据上方错误信息排查。")
        sys.exit(1)


if __name__ == "__main__":
    main()
