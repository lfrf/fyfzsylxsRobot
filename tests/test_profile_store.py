from services.profile.memory_store import MemoryStore
from services.profile.profile_store import ProfileStore
from services.profile.schemas import MemoryEvent


def test_profile_store_creates_files(tmp_path) -> None:
    store = ProfileStore(tmp_path / "profiles")

    profile = store.ensure_user("user_test_001", display_name="小明", face_id="face_001")

    assert profile.user_id == "user_test_001"
    assert profile.display_name == "小明"
    assert "face_001" in profile.face_ids
    assert store.get_user_id_for_face("face_001") == "user_test_001"
    assert store.snapshot_json_path("user_test_001").exists()
    assert store.snapshot_md_path("user_test_001").exists()


def test_memory_store_appends_jsonl(tmp_path) -> None:
    memories = MemoryStore(tmp_path / "profiles")
    event = MemoryEvent(
        user_id="user_test_001",
        session_id="session",
        turn_id="turn-1",
        mode="care",
        asr_text="我今天有点累",
        reply_text="先休息一下。",
    )

    memories.append_event(event)

    events = memories.read_events("user_test_001")
    assert len(events) == 1
    assert events[0].asr_text == "我今天有点累"
