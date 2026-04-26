import json
from pathlib import Path

from config import settings


class VisionStorage:
    def __init__(self) -> None:
        self.root = Path(settings.tmp_dir).expanduser()
        self.root.mkdir(parents=True, exist_ok=True)

    def _turn_dir(self, session_id: str, turn_id: int) -> Path:
        turn_dir = self.root / session_id / str(turn_id)
        turn_dir.mkdir(parents=True, exist_ok=True)
        return turn_dir

    def persist_payload(self, *, session_id: str, turn_id: int, file_name: str, payload: dict) -> Path:
        output_path = self._turn_dir(session_id, turn_id) / file_name
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return output_path


vision_storage = VisionStorage()
