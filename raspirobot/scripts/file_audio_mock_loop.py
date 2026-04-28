from __future__ import annotations

import argparse

from raspirobot.main import run_file_once


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a file wav through the local mock robot loop.")
    parser.add_argument("--wav", required=True, help="Path to an existing wav file.")
    parser.add_argument("--local-playback", action="store_true", help="Use configured local playback provider.")
    args = parser.parse_args()
    run_file_once(args.wav, use_mock_remote=True, mock_playback=not args.local_playback)


if __name__ == "__main__":
    main()
