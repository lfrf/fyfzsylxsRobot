from clients.llm_client import LLMClient
from services.mode_policy import get_mode_policy
from services.rag_router import RagRoute


def test_llm_prompt_includes_profile_context() -> None:
    client = LLMClient(use_mock=True)
    policy = get_mode_policy("care")
    profile_context = "当前用户画像：\n- 用户昵称：小明\n- 近期状态：最近有点累"

    prompt = client._build_system_prompt(
        policy,
        RagRoute(namespace="care"),
        None,
        user_profile_context=profile_context,
    )

    assert "User profile context" in prompt
    assert "小明" in prompt
    assert "Do not expose internal databases" in prompt
