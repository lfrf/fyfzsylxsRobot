"""Tests for P1-1: few-shot and output_constraints loading."""

from clients.llm_client import LLMClient
from services.mode_policy import get_mode_policy
from services.rag_router import RagRoute


def test_care_policy_loads_few_shots() -> None:
    """Verify care mode policy loads few_shots."""
    policy = get_mode_policy("care")
    assert policy.few_shots
    assert "示例" in policy.few_shots
    assert "用户说累" in policy.few_shots or "好的回复" in policy.few_shots


def test_care_policy_loads_output_constraints() -> None:
    """Verify care mode policy loads output_constraints."""
    policy = get_mode_policy("care")
    assert policy.output_constraints
    assert "长度约束" in policy.output_constraints or "120" in policy.output_constraints


def test_accompany_policy_loads_few_shots() -> None:
    """Verify accompany mode policy loads few_shots."""
    policy = get_mode_policy("accompany")
    assert policy.few_shots
    assert "示例" in policy.few_shots or "无聊" in policy.few_shots


def test_accompany_policy_loads_output_constraints() -> None:
    """Verify accompany mode policy loads output_constraints."""
    policy = get_mode_policy("accompany")
    assert policy.output_constraints
    assert "陪伴模式" in policy.output_constraints or "自然陪聊" in policy.output_constraints


def test_learning_policy_loads_few_shots() -> None:
    """Verify learning mode policy loads few_shots."""
    policy = get_mode_policy("learning")
    assert policy.few_shots
    assert "示例" in policy.few_shots or "复习" in policy.few_shots


def test_learning_policy_loads_output_constraints() -> None:
    """Verify learning mode policy loads output_constraints."""
    policy = get_mode_policy("learning")
    assert policy.output_constraints
    assert "学习模式" in policy.output_constraints or "220" in policy.output_constraints


def test_llm_prompt_includes_few_shots_when_present() -> None:
    """Verify LLM prompt includes few_shots when available."""
    client = LLMClient(use_mock=True)
    policy = get_mode_policy("care")

    # Verify policy has few_shots
    assert policy.few_shots

    prompt = client._build_system_prompt(policy, RagRoute(namespace=policy.rag_namespace), None)

    # Verify prompt includes few_shots marker
    assert "## 示例" in prompt
    assert "用户说累" in prompt or "好的回复" in prompt


def test_llm_prompt_includes_output_constraints_when_present() -> None:
    """Verify LLM prompt includes output_constraints when available."""
    client = LLMClient(use_mock=True)
    policy = get_mode_policy("care")

    # Verify policy has output_constraints
    assert policy.output_constraints

    prompt = client._build_system_prompt(policy, RagRoute(namespace=policy.rag_namespace), None)

    # Verify prompt includes output_constraints marker
    assert "## 输出约束" in prompt
    assert "长度约束" in prompt or "120" in prompt


def test_all_three_modes_have_few_shots_and_constraints() -> None:
    """Verify all three active modes have both few_shots and output_constraints."""
    for mode_id in ("care", "accompany", "learning"):
        policy = get_mode_policy(mode_id)
        assert policy.few_shots, f"{mode_id} mode missing few_shots"
        assert policy.output_constraints, f"{mode_id} mode missing output_constraints"
        assert policy.few_shot_path, f"{mode_id} mode missing few_shot_path"
        assert policy.output_constraint_path, f"{mode_id} mode missing output_constraint_path"


def test_game_mode_does_not_require_few_shots() -> None:
    """Verify game mode doesn't error if few_shots/constraints are empty."""
    policy = get_mode_policy("game")
    # Game mode can have empty few_shots/output_constraints for now
    client = LLMClient(use_mock=True)
    prompt = client._build_system_prompt(policy, RagRoute(namespace=policy.rag_namespace), None)
    # Prompt should still be valid even without few_shots/output_constraints
    assert "你现在处于" in prompt and "游戏模式" in prompt


def test_llm_prompt_structure_order() -> None:
    """Verify LLM prompt is assembled in correct order."""
    client = LLMClient(use_mock=True)
    policy = get_mode_policy("care")

    prompt = client._build_system_prompt(policy, RagRoute(namespace=policy.rag_namespace), None)

    # Verify order: instruction comes before few_shots, few_shots before output_constraints
    instruction_pos = prompt.find("你现在处于")
    few_shots_pos = prompt.find("## 示例")
    output_constraints_pos = prompt.find("## 输出约束")
    tts_constraints_pos = prompt.find("【语音输出约束】")

    assert instruction_pos >= 0
    assert few_shots_pos > instruction_pos
    assert output_constraints_pos > few_shots_pos
    assert tts_constraints_pos > output_constraints_pos
