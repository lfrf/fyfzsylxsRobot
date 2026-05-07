from fastapi.testclient import TestClient

import routes.profiles as profile_routes
from app import app
from services.profile.memory_store import MemoryStore
from services.profile.profile_store import ProfileStore
from services.profile.user_profile_service import UserProfileService


def test_profile_api_get_and_summarize(tmp_path, monkeypatch) -> None:
    root = tmp_path / "profiles"
    store = ProfileStore(root)
    memories = MemoryStore(root)
    service = UserProfileService(store=store, memories=memories)
    store.ensure_user("user_api_001", display_name="小明", face_id="face_api_001")

    monkeypatch.setattr(profile_routes, "profile_store", store)
    monkeypatch.setattr(profile_routes, "memory_store", memories)
    monkeypatch.setattr(profile_routes, "user_profile_service", service)

    client = TestClient(app)

    by_user = client.get("/v1/profiles/user_api_001")
    assert by_user.status_code == 200
    assert by_user.json()["profile"]["display_name"] == "小明"

    by_face = client.get("/v1/profiles/by-face/face_api_001")
    assert by_face.status_code == 200
    assert by_face.json()["profile"]["user_id"] == "user_api_001"

    resolved = client.post(
        "/v1/profiles/resolve-face",
        json={"session_id": "session-api", "face_id": "face_api_late", "source": "raspi_identity_watcher"},
    )
    assert resolved.status_code == 200
    assert resolved.json()["identity"]["user_id"] == "user_face_api_late"
    assert resolved.json()["identity"]["display_name"] is None

    summarized = client.post("/v1/profiles/user_api_001/summarize")
    assert summarized.status_code == 200
    assert "summary" in summarized.json()
