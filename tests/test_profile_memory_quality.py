from services.output_control.profile_context_composer import ProfileContextComposer
from services.profile.memory_store import MemoryStore
from services.profile.profile_builder import ProfileBuilder
from services.profile.profile_store import ProfileStore
from services.profile.schemas import MemoryEvent
from services.profile.user_profile_service import UserProfileService


def test_user_profile_service_filters_noise_memory(tmp_path) -> None:
    store = ProfileStore(tmp_path)
    memories = MemoryStore(tmp_path)
    service = UserProfileService(store=store, memories=memories, builder=ProfileBuilder())
    profile = store.ensure_user("user_noise", display_name="小周")

    result = service.record_turn(
        user_id=profile.user_id,
        session_id="s1",
        turn_id="t1",
        mode_id="care",
        asr_text="测试一下你能听见我吗",
        reply_text="能听见。",
    )

    assert result.written is False
    assert result.memory_type == "noise"
    assert memories.read_events(profile.user_id) == []


def test_user_profile_service_applies_profile_patch(tmp_path) -> None:
    store = ProfileStore(tmp_path)
    memories = MemoryStore(tmp_path)
    service = UserProfileService(store=store, memories=memories, builder=ProfileBuilder())
    profile = store.ensure_user("user_patch")

    result = service.record_turn(
        user_id=profile.user_id,
        session_id="s1",
        turn_id="t1",
        mode_id="learning",
        asr_text="我叫小周，我最近在准备嵌入式系统考试，担心 UART 和 ADC，我喜欢简洁回答。",
        reply_text="记住了。",
    )
    updated = store.get_profile(profile.user_id)

    assert result.written is True
    assert result.memory_type == "identity"
    assert updated is not None
    assert updated.display_name == "小周"
    assert updated.interaction_style.get("prefers_short_replies") is True
    assert "UART" in updated.recent_topics
    assert "ADC" in updated.recent_topics


def test_profile_context_composer_avoids_raw_noise_memory(tmp_path) -> None:
    profile = ProfileStore(tmp_path).ensure_user("context_user", display_name="小周")
    profile.interaction_style["prefers_short_replies"] = True
    profile.learning_goals.append("准备嵌入式系统考试")
    memories = [
        MemoryEvent(
            user_id=profile.user_id,
            session_id="s1",
            turn_id="t1",
            mode="care",
            asr_text="测试一下你能听见我吗",
            reply_text="能听见。",
            memory_type="noise",
        ),
        MemoryEvent(
            user_id=profile.user_id,
            session_id="s1",
            turn_id="t2",
            mode="learning",
            asr_text="我担心 UART 和 ADC",
            reply_text="我们可以拆开复习。",
            memory_type="learning_goal",
        ),
    ]

    context = ProfileContextComposer().compose(profile=profile, recent_memories=memories, mode_id="care")

    assert "小周" in context
    assert "简洁回答" in context
    assert "UART" in context
    assert "测试一下" not in context
    assert "memory" not in context.lower()
