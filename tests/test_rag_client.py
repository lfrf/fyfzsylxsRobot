from clients.rag_client import RAGClient


def test_care_namespace_reads_markdown_knowledge_base() -> None:
    context = RAGClient().retrieve_context(namespace="care", query="我想有人陪我聊聊天")

    assert context is not None
    assert "【来源：" in context
    assert "04_loneliness_and_companionship.md" in context or "01_emotional_comfort_phrases.md" in context


def test_care_fatigue_query_prefers_rest_and_comfort_docs() -> None:
    context = RAGClient().retrieve_context(namespace="care", query="我今天有点累")

    assert context is not None
    assert "【来源：" in context
    assert (
        "02_daily_life_reminders.md" in context
        or "05_sleep_and_rest_support.md" in context
        or "01_emotional_comfort_phrases.md" in context
    )
    assert "休息" in context or "喝水" in context or "陪着你" in context


def test_care_safety_query_prefers_boundary_docs() -> None:
    context = RAGClient().retrieve_context(namespace="care", query="我头晕胸口痛")

    assert context is not None
    assert "03_elderly_safety_boundaries.md" in context
    assert "99_forbidden_medical_claims.md" in context
    assert "联系家人" in context or "医生" in context


def test_unknown_namespace_returns_none() -> None:
    assert RAGClient().retrieve_context(namespace="unknown_namespace", query="你好") is None
