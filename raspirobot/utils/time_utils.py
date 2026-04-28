from __future__ import annotations

from datetime import UTC, datetime
from time import time


def unix_timestamp() -> float:
    return time()


def utc_compact_timestamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
