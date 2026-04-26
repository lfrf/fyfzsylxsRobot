import json
from pathlib import Path
import shutil

from config import settings


class AvatarStorage:
    def __init__(self) -> None:
        self.root = Path(settings.tmp_dir).expanduser()
        self.root.mkdir(parents=True, exist_ok=True)

    def _turn_dir(self, session_id: str, turn_id: int) -> Path:
        turn_dir = self.root / session_id / str(turn_id)
        turn_dir.mkdir(parents=True, exist_ok=True)
        return turn_dir

    def persist_output(self, *, session_id: str, turn_id: int, payload: dict) -> Path:
        output_path = self._turn_dir(session_id, turn_id) / "avatar_output.json"
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return output_path

    def persist_audio(self, *, session_id: str, turn_id: int, audio_bytes: bytes) -> Path:
        output_path = self._turn_dir(session_id, turn_id) / "reply.wav"
        output_path.write_bytes(audio_bytes)
        return output_path

    def get_audio_path(self, *, session_id: str, turn_id: int) -> Path:
        return self._turn_dir(session_id, turn_id) / "reply.wav"

    def persist_video(self, *, session_id: str, turn_id: int, source_path: str | Path) -> Path:
        output_path = self._turn_dir(session_id, turn_id) / "reply.mp4"
        shutil.copy2(Path(source_path), output_path)
        return output_path

    def get_video_path(self, *, session_id: str, turn_id: int) -> Path:
        return self._turn_dir(session_id, turn_id) / "reply.mp4"

    def persist_video_chunk(self, *, session_id: str, turn_id: int, chunk_index: int, source_path: str | Path) -> Path:
        chunk_dir = self._turn_dir(session_id, turn_id) / "video_chunks"
        chunk_dir.mkdir(parents=True, exist_ok=True)
        output_path = chunk_dir / f"chunk-{chunk_index:04d}.mp4"
        shutil.copy2(Path(source_path), output_path)
        return output_path

    def get_video_chunk_path(self, *, session_id: str, turn_id: int, chunk_index: int) -> Path:
        chunk_dir = self._turn_dir(session_id, turn_id) / "video_chunks"
        return chunk_dir / f"chunk-{chunk_index:04d}.mp4"

    def persist_video_manifest(self, *, session_id: str, turn_id: int, payload: dict) -> Path:
        output_path = self._turn_dir(session_id, turn_id) / "video_manifest.json"
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return output_path

    def get_video_manifest_path(self, *, session_id: str, turn_id: int) -> Path:
        return self._turn_dir(session_id, turn_id) / "video_manifest.json"

    def persist_runtime_error(self, *, session_id: str, turn_id: int, payload: dict) -> Path:
        output_path = self._turn_dir(session_id, turn_id) / "tts_runtime_error.json"
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return output_path


avatar_storage = AvatarStorage()
