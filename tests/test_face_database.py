import sys
from pathlib import Path


def _use_vision_service(monkeypatch, tmp_path):
    vision_root = Path(__file__).resolve().parents[1] / "remote" / "vision-service"
    monkeypatch.syspath_prepend(str(vision_root))
    monkeypatch.setenv("FACE_DB_DIR", str(tmp_path / "faces"))
    monkeypatch.setenv("FACE_RECOGNITION_PROVIDER", "mock")
    for module_name in list(sys.modules):
        if module_name in {"config", "models", "app", "services", "routes"}:
            monkeypatch.delitem(sys.modules, module_name, raising=False)
        elif module_name.startswith(("services.", "routes.")):
            monkeypatch.delitem(sys.modules, module_name, raising=False)


def test_face_database_matches_and_updates_seen_count(monkeypatch, tmp_path) -> None:
    _use_vision_service(monkeypatch, tmp_path)

    from services.face_database import FaceDatabase

    database = FaceDatabase(tmp_path / "faces")
    first = database.match_or_create(
        embedding=[1.0, 0.0, 0.0],
        threshold=0.6,
        create_unknown=True,
        source="test",
        embedding_model="unit",
    )
    second = database.match_or_create(
        embedding=[1.0, 0.0, 0.0],
        threshold=0.6,
        create_unknown=True,
        source="test",
        embedding_model="unit",
    )

    assert first.record is not None
    assert second.record is not None
    assert first.record["face_id"] == second.record["face_id"]
    assert second.created is False
    assert second.record["seen_count"] == 2
    assert database.db_path.exists()
