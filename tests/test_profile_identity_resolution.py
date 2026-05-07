from types import SimpleNamespace

from services.profile.memory_store import MemoryStore
from services.profile.profile_store import ProfileStore
from services.profile.user_profile_service import UserProfileService


def _service(tmp_path) -> UserProfileService:
    root = tmp_path / "profiles"
    return UserProfileService(store=ProfileStore(root), memories=MemoryStore(root))


def test_mock_user_id_takes_priority(tmp_path) -> None:
    service = _service(tmp_path)
    request = SimpleNamespace(
        session_id="session-1",
        request_options={"mock_user_id": "user_mock_001", "mock_display_name": "小明", "face_id": "face_ignored"},
        vision_context=None,
    )

    identity = service.resolve_identity(request)

    assert identity.user_id == "user_mock_001"
    assert identity.display_name == "小明"
    assert identity.identity_source == "mock_user_id"


def test_face_id_creates_user_mapping(tmp_path) -> None:
    service = _service(tmp_path)
    request = SimpleNamespace(
        session_id="session-1",
        request_options={"face_id": "face_abc"},
        vision_context=None,
    )

    identity = service.resolve_identity(request)

    assert identity.identity_source == "face_id"
    assert identity.face_id == "face_abc"
    assert service.store.get_user_id_for_face("face_abc") == identity.user_id


def test_anonymous_session_fallback(tmp_path) -> None:
    service = _service(tmp_path)
    request = SimpleNamespace(session_id="session-xyz", request_options={}, vision_context=None)

    identity = service.resolve_identity(request)

    assert identity.user_id is None
    assert identity.identity_source == "no_face"
    assert identity.is_anonymous is True
    assert identity.persisted is False
    assert service.store._load_users_index() == {"users": {}}
