from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class TurnLogger:
    log_path: str | Path | None = None
    records: list[dict[str, Any]] = field(default_factory=list)

    def log(self, record: dict[str, Any]) -> None:
        self.records.append(record)
        if self.log_path is None:
            return
        path = Path(self.log_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
