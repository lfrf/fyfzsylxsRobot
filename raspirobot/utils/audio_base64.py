from __future__ import annotations

import base64
from pathlib import Path


def encode_file_to_base64(path: str | Path) -> str:
    data = Path(path).read_bytes()
    return base64.b64encode(data).decode("ascii")


def decode_base64_to_file(audio_base64: str, path: str | Path) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(base64.b64decode(audio_base64))
    return output
