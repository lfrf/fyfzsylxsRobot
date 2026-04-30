from clients.rag_client import RAGClient


def test_care_namespace_reads_markdown_knowledge_base() -> None:
    client = RAGClient()
    context = client.retrieve_context(namespace="care", query="我想有人陪我聊聊天")

    assert context is not None
    assert "【来源：" in context
    assert "04_loneliness_and_companionship.md" in context or "01_emotional_comfort_phrases.md" in context
    assert client.last_matched_files
    assert client.last_context_chars == len(context)


def test_care_fatigue_query_prefers_rest_and_comfort_docs() -> None:
    client = RAGClient()
    context = client.retrieve_context(namespace="care", query="我今天有点累")

    assert context is not None
    assert "【来源：" in context
    assert (
        "02_daily_life_reminders.md" in context
        or "05_sleep_and_rest_support.md" in context
        or "01_emotional_comfort_phrases.md" in context
    )
    assert "休息" in context or "喝水" in context or "陪着你" in context
    assert client.last_matched_files


def test_care_safety_query_prefers_boundary_docs() -> None:
    client = RAGClient()
    context = client.retrieve_context(namespace="care", query="我头晕胸口痛")

    assert context is not None
    assert "03_elderly_safety_boundaries.md" in context
    assert "99_forbidden_medical_claims.md" in context
    assert "联系家人" in context or "医生" in context
    assert client.last_matched_files[:2] == [
        "03_elderly_safety_boundaries.md",
        "99_forbidden_medical_claims.md",
    ]


def test_unknown_namespace_returns_none() -> None:
    client = RAGClient()

    assert client.retrieve_context(namespace="unknown_namespace", query="你好") is None
    assert client.last_matched_files == []
    assert client.last_context_chars == 0
