from __future__ import annotations

from pathlib import Path


def ensure_dir(path: str | Path) -> Path:
    directory = Path(path)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def safe_child_name(value: str) -> str:
    cleaned = [char if char.isalnum() or char in {"-", "_", "."} else "_" for char in value]
    name = "".join(cleaned).strip("._")
    return name or "item"
