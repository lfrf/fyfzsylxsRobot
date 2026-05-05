import base64
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


def test_mock_identity_service_creates_then_matches_face(monkeypatch, tmp_path) -> None:
    _use_vision_service(monkeypatch, tmp_path)

    from models import FaceIdentityRequest
    from services.face_database import FaceDatabase
    from services.face_embedding_runtime import FaceEmbeddingRuntime
    from services.face_identity_service import FaceIdentityService

    service = FaceIdentityService(
        database=FaceDatabase(tmp_path / "faces"),
        runtime=FaceEmbeddingRuntime(provider="mock"),
    )
    image_base64 = base64.b64encode(b"stable-face-image").decode("ascii")
    request = FaceIdentityRequest(session_id="s1", turn_id="t1", image_base64=image_base64)

    first = service.extract_identity(request)
    second = service.extract_identity(request)

    assert first.face_identity is not None
    assert second.face_identity is not None
    assert first.face_identity.face_detected is True
    assert first.face_identity.face_id == second.face_identity.face_id
    assert first.face_identity.is_known is False
    assert second.face_identity.is_known is True
    assert second.face_identity.seen_count == 2
    assert second.face_observations[0].is_primary is True
    assert second.provider == "mock"


def test_insightface_provider_is_lazy_and_skippable(monkeypatch, tmp_path) -> None:
    _use_vision_service(monkeypatch, tmp_path)

    import pytest

    from services.face_embedding_runtime import FaceEmbeddingRuntime

    runtime = FaceEmbeddingRuntime(provider="insightface")
    pytest.importorskip("insightface")
    pytest.importorskip("cv2")
    assert runtime.provider == "insightface"
