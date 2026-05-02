from __future__ import annotations

import argparse
from time import sleep

from raspirobot.config import load_settings
from raspirobot.main import build_eyes_driver


def main() -> None:
    parser = argparse.ArgumentParser(description="Cycle eye expressions on ST7789 displays.")
    parser.add_argument(
        "--expressions",
        nargs="+",
        default=["neutral", "happy", "sad", "blink"],
        help="Expression names mapped to files/dirs in ROBOT_EYES_ASSETS_DIR.",
    )
    parser.add_argument("--hold-seconds", type=float, default=2.0)
    parser.add_argument("--loops", type=int, default=0, help="0 means infinite loop.")
    args = parser.parse_args()

    settings = load_settings()
    eyes = build_eyes_driver(settings)
    loop_count = 0
    while args.loops == 0 or loop_count < args.loops:
        loop_count += 1
        for expression in args.expressions:
            print(f"[eyes-demo] expression={expression}")
            eyes.set_expression(expression)
            sleep(max(0.1, args.hold_seconds))


if __name__ == "__main__":
    main()
