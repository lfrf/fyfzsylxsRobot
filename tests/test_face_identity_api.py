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


def test_face_identity_api_keeps_extract_route_and_returns_face_id(monkeypatch, tmp_path) -> None:
    _use_vision_service(monkeypatch, tmp_path)

    from fastapi.testclient import TestClient

    from app import app

    client = TestClient(app)
    image_base64 = base64.b64encode(b"api-face-image").decode("ascii")

    first = client.post(
        "/v1/vision/identity/extract",
        json={"session_id": "s1", "turn_id": "t1", "image_base64": image_base64},
    )
    second = client.post(
        "/v1/vision/identity/extract",
        json={"session_id": "s1", "turn_id": "t2", "image_base64": image_base64},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    first_payload = first.json()
    second_payload = second.json()
    assert first_payload["face_identity"]["face_detected"] is True
    assert first_payload["face_identity"]["face_id"] == second_payload["face_identity"]["face_id"]
    assert second_payload["face_identity"]["is_known"] is True
    assert second_payload["provider"] == "mock"
    assert any(route.path == "/extract" for route in app.routes)
