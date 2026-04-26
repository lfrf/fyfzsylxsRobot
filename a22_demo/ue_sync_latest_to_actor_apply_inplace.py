#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UE helper entrypoint:
Always run ue_sync_latest_to_actor.py with --apply-viseme-inplace.

Usage in Unreal console:
  Cmd: py "C:/Users/FYF/Documents/GitHub/FuChuangSai_A22/a22_demo/ue_sync_latest_to_actor_apply_inplace.py"
"""

from __future__ import annotations

from pathlib import Path
import runpy
import sys


def main() -> int:
    script_path = Path(__file__).with_name("ue_sync_latest_to_actor.py")
    sys.argv = [
        str(script_path),
        "--apply-viseme-inplace",
        "--dump-viseme-schema",
    ]
    runpy.run_path(str(script_path), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
