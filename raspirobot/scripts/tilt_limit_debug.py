from __future__ import annotations

import argparse
import time

from raspirobot.hardware.pan_tilt_face_tracker import (
    PanTiltServoConfig,
    PanTiltServoDriver,
    ServoSpec,
)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Tilt-only servo limit debug tool. Pan stays fixed while tilt moves."
    )
    parser.add_argument("--mode", choices=["sweep", "interactive", "both"], default="both")

    parser.add_argument("--i2c-address", type=lambda x: int(x, 0), default=0x40)
    parser.add_argument("--frequency", type=int, default=50)
    parser.add_argument("--pan-channel", type=int, default=0)
    parser.add_argument("--tilt-channel", type=int, default=1)

    parser.add_argument("--servo-min-pulse", type=int, default=500)
    parser.add_argument("--servo-max-pulse", type=int, default=2500)
    parser.add_argument("--actuation-range", type=float, default=270.0)

    parser.add_argument("--pan-center", type=float, default=135.0)
    parser.add_argument("--tilt-center", type=float, default=135.0)
    parser.add_argument("--pan-min-angle", type=float, default=0.0)
    parser.add_argument("--pan-max-angle", type=float, default=270.0)
    parser.add_argument("--tilt-min-angle", type=float, default=35.0)
    parser.add_argument("--tilt-max-angle", type=float, default=235.0)

    parser.add_argument("--pan-zero-offset", type=float, default=0.0)
    parser.add_argument("--tilt-zero-offset", type=float, default=0.0)

    parser.set_defaults(pan_inverted=True, tilt_inverted=True)
    parser.add_argument("--pan-inverted", dest="pan_inverted", action="store_true")
    parser.add_argument("--no-pan-inverted", dest="pan_inverted", action="store_false")
    parser.add_argument("--tilt-inverted", dest="tilt_inverted", action="store_true")
    parser.add_argument("--no-tilt-inverted", dest="tilt_inverted", action="store_false")

    parser.add_argument("--step-deg", type=float, default=5.0, help="Tilt step in degrees.")
    parser.add_argument("--dwell-ms", type=int, default=600, help="Pause between sweep positions.")
    parser.add_argument("--sweep-cycles", type=int, default=1, help="Number of max->min->center cycles.")
    parser.add_argument("--park-center-on-exit", action="store_true")
    return parser


def build_driver(args: argparse.Namespace) -> PanTiltServoDriver:
    pan_spec = ServoSpec(
        model_name="LD-3015MG",
        min_pulse_us=args.servo_min_pulse,
        max_pulse_us=args.servo_max_pulse,
        actuation_range_deg=args.actuation_range,
        safe_min_angle_deg=args.pan_min_angle,
        safe_max_angle_deg=args.pan_max_angle,
        center_angle_deg=args.pan_center,
    )
    tilt_spec = ServoSpec(
        model_name="LD-3015MG",
        min_pulse_us=args.servo_min_pulse,
        max_pulse_us=args.servo_max_pulse,
        actuation_range_deg=args.actuation_range,
        safe_min_angle_deg=args.tilt_min_angle,
        safe_max_angle_deg=args.tilt_max_angle,
        center_angle_deg=args.tilt_center,
    )
    cfg = PanTiltServoConfig(
        i2c_address=args.i2c_address,
        frequency_hz=args.frequency,
        pan_channel=args.pan_channel,
        tilt_channel=args.tilt_channel,
        pan_inverted=args.pan_inverted,
        tilt_inverted=args.tilt_inverted,
        pan_zero_offset_deg=args.pan_zero_offset,
        tilt_zero_offset_deg=args.tilt_zero_offset,
        pan_spec=pan_spec,
        tilt_spec=tilt_spec,
    )
    return PanTiltServoDriver(cfg)


def clamp(value: float, low: float, high: float) -> float:
    if value < low:
        return low
    if value > high:
        return high
    return value


def move_tilt(
    servo: PanTiltServoDriver,
    *,
    pan_fixed: float,
    tilt_target: float,
    tilt_min: float,
    tilt_max: float,
) -> float:
    tilt_clamped = clamp(tilt_target, tilt_min, tilt_max)
    servo.set_pose(pan_fixed, tilt_clamped)
    print(f"[tilt-debug] pan={servo.pan_deg:.1f} tilt={servo.tilt_deg:.1f}")
    return servo.tilt_deg


def run_sweep(servo: PanTiltServoDriver, args: argparse.Namespace) -> None:
    step = abs(args.step_deg)
    if step <= 0:
        raise ValueError("--step-deg must be > 0")
    dwell_s = max(0.0, args.dwell_ms / 1000.0)
    pan_fixed = args.pan_center
    tilt_min = args.tilt_min_angle
    tilt_max = args.tilt_max_angle
    tilt_center = clamp(args.tilt_center, tilt_min, tilt_max)

    print(
        f"[tilt-debug] sweep start: pan fixed at {pan_fixed:.1f}, "
        f"tilt range [{tilt_min:.1f}, {tilt_max:.1f}], center {tilt_center:.1f}"
    )
    move_tilt(
        servo,
        pan_fixed=pan_fixed,
        tilt_target=tilt_center,
        tilt_min=tilt_min,
        tilt_max=tilt_max,
    )
    time.sleep(dwell_s)

    for cycle in range(max(1, args.sweep_cycles)):
        print(f"[tilt-debug] cycle {cycle + 1}/{max(1, args.sweep_cycles)}")

        pos = tilt_center
        while pos < tilt_max:
            pos = min(tilt_max, pos + step)
            move_tilt(
                servo,
                pan_fixed=pan_fixed,
                tilt_target=pos,
                tilt_min=tilt_min,
                tilt_max=tilt_max,
            )
            time.sleep(dwell_s)

        pos = tilt_max
        while pos > tilt_min:
            pos = max(tilt_min, pos - step)
            move_tilt(
                servo,
                pan_fixed=pan_fixed,
                tilt_target=pos,
                tilt_min=tilt_min,
                tilt_max=tilt_max,
            )
            time.sleep(dwell_s)

        pos = tilt_min
        while pos < tilt_center:
            pos = min(tilt_center, pos + step)
            move_tilt(
                servo,
                pan_fixed=pan_fixed,
                tilt_target=pos,
                tilt_min=tilt_min,
                tilt_max=tilt_max,
            )
            time.sleep(dwell_s)

    print("[tilt-debug] sweep done")


def run_interactive(servo: PanTiltServoDriver, args: argparse.Namespace) -> None:
    pan_fixed = args.pan_center
    tilt_min = args.tilt_min_angle
    tilt_max = args.tilt_max_angle
    current = clamp(args.tilt_center, tilt_min, tilt_max)
    step = abs(args.step_deg)

    current = move_tilt(
        servo,
        pan_fixed=pan_fixed,
        tilt_target=current,
        tilt_min=tilt_min,
        tilt_max=tilt_max,
    )
    print("[tilt-debug] interactive commands:")
    print("  + / u       : tilt up by step")
    print("  - / d       : tilt down by step")
    print("  min         : move to tilt min")
    print("  max         : move to tilt max")
    print("  center      : move to tilt center")
    print("  step <deg>  : set step size")
    print("  <number>    : move to absolute tilt angle")
    print("  q           : quit")

    while True:
        cmd = input("tilt-debug> ").strip().lower()
        if not cmd:
            continue
        if cmd in {"q", "quit", "exit"}:
            break
        if cmd.startswith("step "):
            try:
                new_step = float(cmd.split(" ", 1)[1])
                if new_step <= 0:
                    print("[tilt-debug] step must be > 0")
                    continue
                step = new_step
                print(f"[tilt-debug] step={step:.2f}")
            except ValueError:
                print("[tilt-debug] invalid step value")
            continue

        if cmd in {"+", "u", "up"}:
            target = current + step
        elif cmd in {"-", "d", "down"}:
            target = current - step
        elif cmd == "min":
            target = tilt_min
        elif cmd == "max":
            target = tilt_max
        elif cmd == "center":
            target = clamp(args.tilt_center, tilt_min, tilt_max)
        else:
            try:
                target = float(cmd)
            except ValueError:
                print("[tilt-debug] unknown command")
                continue

        current = move_tilt(
            servo,
            pan_fixed=pan_fixed,
            tilt_target=target,
            tilt_min=tilt_min,
            tilt_max=tilt_max,
        )

    print("[tilt-debug] interactive mode ended")


def main() -> None:
    args = build_arg_parser().parse_args()
    servo = build_driver(args)

    try:
        if args.mode in {"sweep", "both"}:
            run_sweep(servo, args)
        if args.mode in {"interactive", "both"}:
            run_interactive(servo, args)
    except KeyboardInterrupt:
        print("\n[tilt-debug] interrupted")
    finally:
        if args.park_center_on_exit:
            move_tilt(
                servo,
                pan_fixed=args.pan_center,
                tilt_target=args.tilt_center,
                tilt_min=args.tilt_min_angle,
                tilt_max=args.tilt_max_angle,
            )
            print("[tilt-debug] parked at center")


if __name__ == "__main__":
    main()
