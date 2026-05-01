#!/usr/bin/env python3
"""
Audio capture and preprocessing debug script.

Two modes:
  1. Capture from microphone: Record audio and run preprocessor
  2. Process existing WAV: Load existing WAV and run preprocessor

Shows readable metrics and debug JSON output.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from raspirobot.audio.preprocessor import AudioPreprocessor, AudioPreprocessConfig
from raspirobot.config import load_settings


def capture_mode(
    seconds: int,
    sample_rate: int,
    channels: int,
    output_dir: Path,
    frame_ms: int,
    gate_ratio: float,
    trim_enabled: bool,
) -> None:
    """Capture audio from microphone and process."""
    try:
        import subprocess
    except ImportError:
        print("Error: subprocess module not found")
        sys.exit(1)

    print(f"Recording {seconds} seconds at {sample_rate}Hz, {channels} channel(s)...")
    wav_path = output_dir / "captured_audio.wav"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Use arecord to capture audio
    cmd = [
        "arecord",
        "-t", "wav",
        "-f", "S16_LE",
        "-r", str(sample_rate),
        "-c", str(channels),
        "-d", str(seconds),
        str(wav_path),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
    except FileNotFoundError:
        print("Error: arecord not found. Install it with: apt-get install alsa-utils")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"Error: arecord failed: {e.stderr.decode() if e.stderr else e}")
        sys.exit(1)

    print(f"✓ Saved to {wav_path}")
    process_wav(wav_path, output_dir, frame_ms, gate_ratio, trim_enabled)


def process_wav(
    wav_path: Path | str,
    output_dir: Path | None = None,
    frame_ms: int = 30,
    gate_ratio: float = 3.0,
    trim_enabled: bool = True,
) -> None:
    """Load existing WAV and run preprocessor."""
    wav_path = Path(wav_path)
    if not wav_path.exists():
        print(f"Error: WAV file not found: {wav_path}")
        sys.exit(1)

    output_dir = output_dir or wav_path.parent

    config = AudioPreprocessConfig(
        enabled=True,
        enable_noise_gate=True,
        enable_trim=trim_enabled,
        frame_ms=frame_ms,
        noise_gate_ratio=gate_ratio,
        save_debug_wav=True,
        debug_dir=output_dir,
    )
    preprocessor = AudioPreprocessor(config)

    print(f"\nProcessing: {wav_path}")
    print(f"  Frame: {frame_ms}ms")
    print(f"  Gate ratio: {gate_ratio}")
    print(f"  Trim enabled: {trim_enabled}")

    result = preprocessor.process_file(wav_path, output_dir=output_dir)

    print("\n=== PREPROCESSING RESULT ===")
    print(f"Raw WAV path:             {result.raw_wav_path}")
    print(f"Clean WAV path:           {result.clean_wav_path}")
    print(f"Used for payload:         {result.used_for_payload_path}")
    print(f"\nAudio info:")
    print(f"  Raw duration:           {result.raw_duration_ms}ms")
    print(f"  Clean duration:         {result.clean_duration_ms}ms")
    print(f"  Total frames:           {result.total_frames}")
    print(f"  Speech frames:          {result.speech_frames}")
    print(f"  Muted frames:           {result.muted_frames}")
    print(f"\nTrimming:")
    print(f"  Leading frames:         {result.leading_frames_trimmed}")
    print(f"  Trailing frames:        {result.trailing_frames_trimmed}")
    print(f"  Head ms:                {result.trimmed_head_ms}ms")
    print(f"  Tail ms:                {result.trimmed_tail_ms}ms")
    print(f"  Speech duration:        {result.speech_duration_ms}ms")
    print(f"\nNoise analysis:")
    print(f"  Noise floor RMS:        {result.noise_floor_rms:.1f}")
    print(f"  Noise floor strategy:   {result.noise_floor_strategy}")
    print(f"  Gate threshold RMS:     {result.gate_threshold_rms:.1f}")
    print(f"  Speech peak RMS:        {result.speech_peak_rms:.1f}")
    print(f"  Speech mean RMS:        {result.speech_mean_rms:.1f}")
    print(f"\nFallback:")
    print(f"  Fallback used:          {result.fallback_used}")
    print(f"  Fallback reason:        {result.fallback_reason}")

    if result.debug_json_path and result.debug_json_path.exists():
        print(f"\n✓ Debug JSON:              {result.debug_json_path}")
        with open(result.debug_json_path) as f:
            debug_data = json.load(f)
            print(json.dumps(debug_data, indent=2))

    print(f"\n✓ Processed successfully")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audio capture and preprocessing debug tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Capture 10 seconds from microphone and preprocess
  python -m raspirobot.scripts.audio_capture_debug capture --seconds 10

  # Process existing WAV file
  python -m raspirobot.scripts.audio_capture_debug process --input /path/to/audio.wav

  # Process with custom settings
  python -m raspirobot.scripts.audio_capture_debug process --input audio.wav --frame-ms 20 --gate-ratio 4.0
        """,
    )

    subparsers = parser.add_subparsers(dest="mode", required=True, help="Operation mode")

    # Capture mode
    capture_parser = subparsers.add_parser("capture", help="Capture from microphone")
    capture_parser.add_argument("--seconds", type=int, default=5, help="Recording duration in seconds (default: 5)")
    capture_parser.add_argument("--sample-rate", type=int, default=16000, help="Sample rate in Hz (default: 16000)")
    capture_parser.add_argument("--channels", type=int, default=1, help="Number of channels (default: 1)")
    capture_parser.add_argument("--output-dir", type=Path, default=Path.cwd(), help="Output directory (default: current)")
    capture_parser.add_argument("--frame-ms", type=int, default=30, help="Frame size in ms (default: 30)")
    capture_parser.add_argument("--gate-ratio", type=float, default=3.0, help="Noise gate ratio (default: 3.0)")
    capture_parser.add_argument("--no-trim", action="store_true", help="Disable trimming")

    # Process mode
    process_parser = subparsers.add_parser("process", help="Process existing WAV file")
    process_parser.add_argument("--input", type=Path, required=True, help="Input WAV file path")
    process_parser.add_argument("--output-dir", type=Path, help="Output directory (default: input directory)")
    process_parser.add_argument("--frame-ms", type=int, default=30, help="Frame size in ms (default: 30)")
    process_parser.add_argument("--gate-ratio", type=float, default=3.0, help="Noise gate ratio (default: 3.0)")
    process_parser.add_argument("--no-trim", action="store_true", help="Disable trimming")

    args = parser.parse_args()

    try:
        if args.mode == "capture":
            capture_mode(
                seconds=args.seconds,
                sample_rate=args.sample_rate,
                channels=args.channels,
                output_dir=args.output_dir,
                frame_ms=args.frame_ms,
                gate_ratio=args.gate_ratio,
                trim_enabled=not args.no_trim,
            )
        elif args.mode == "process":
            process_wav(
                wav_path=args.input,
                output_dir=args.output_dir,
                frame_ms=args.frame_ms,
                gate_ratio=args.gate_ratio,
                trim_enabled=not args.no_trim,
            )
    except KeyboardInterrupt:
        print("\n✗ Interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n✗ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
