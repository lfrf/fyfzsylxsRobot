from services.profile.profile_builder import ProfileBuilder
from services.profile.schemas import MemoryEvent, UserProfile


def test_profile_builder_summarizes_rules() -> None:
    builder = ProfileBuilder()
    profile = UserProfile(user_id="user_test", display_name="小明")
    events = [
        MemoryEvent(
            user_id="user_test",
            session_id="session",
            turn_id="turn-1",
            mode="learning",
            asr_text="我今天有点累，但想复习课程",
            reply_text="我们慢慢复习。",
        ),
        MemoryEvent(
            user_id="user_test",
            session_id="session",
            turn_id="turn-2",
            mode="game",
            asr_text="我们玩词语接龙",
            reply_text="好呀。",
        ),
    ]

    result = builder.summarize(profile, events)

    assert result.updated is True
    assert profile.preferred_mode in {"learning", "game"}
    assert profile.learning_goals
    assert profile.preferences.get("likes_games") is True
    assert "疲惫" in "".join(profile.emotional_notes)


def test_profile_context_is_compact_and_natural() -> None:
    builder = ProfileBuilder()
    profile = UserProfile(
        user_id="user_test",
        display_name="小明",
        profile_summary="最近有点累，喜欢简短陪伴。",
        preferred_mode="care",
    )

    context = builder.build_context(profile=profile, mode_id="care", max_chars=160)

    assert "当前用户画像" in context
    assert "小明" in context
    assert "数据库" not in context
    assert len(context) <= 160
