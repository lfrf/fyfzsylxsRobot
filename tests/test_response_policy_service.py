"""Tests for ResponsePolicyService."""

import pytest

from services.response_policy_service import ResponsePolicyService


@pytest.fixture
def service() -> ResponsePolicyService:
    """Provide ResponsePolicyService instance."""
    return ResponsePolicyService()


# ===== Universal Rules Tests =====


def test_remove_markdown_headings(service: ResponsePolicyService) -> None:
    """Test removal of markdown heading symbols."""
    reply = "# 这是标题\n## 子标题\n这是内容。"
    result = service.apply(mode_id="accompany", reply_text=reply)
    assert "#" not in result.reply_text
    assert "remove_markdown_headings" in result.rules_applied


def test_remove_table_symbols(service: ResponsePolicyService) -> None:
    """Test removal of table symbols."""
    reply = "| 第一列 | 第二列 |\n| --- | --- |\n| 数据 | 数据 |"
    result = service.apply(mode_id="accompany", reply_text=reply)
    assert "|" not in result.reply_text
    assert "remove_table_symbols" in result.rules_applied


def test_remove_list_symbols(service: ResponsePolicyService) -> None:
    """Test removal of bullet points."""
    reply = "- 第一项\n* 第二项\n1. 第三项"
    result = service.apply(mode_id="accompany", reply_text=reply)
    assert "-" not in result.reply_text or result.reply_text.count("-") == 0
    assert "remove_list_symbols" in result.rules_applied


def test_remove_ai_self_reference(service: ResponsePolicyService) -> None:
    """Test removal of 'AI' self-references."""
    test_cases = [
        "作为一个AI，我可以帮助你。",
        "作为AI语言模型，我的建议是。",
        "我是一个AI助手。",
    ]
    for reply in test_cases:
        result = service.apply(mode_id="accompany", reply_text=reply)
        assert "AI" not in result.reply_text or result.reply_text.count("AI") == 0
        assert "remove_ai_self_reference" in result.rules_applied


def test_remove_stage_directions(service: ResponsePolicyService) -> None:
    """Test removal of stage directions."""
    test_cases = [
        "好的。（点头）我同意。",
        "你说得对。[微笑] 我很高兴。",
        "【认真思考】这个问题很有意思。",
    ]
    for reply in test_cases:
        result = service.apply(mode_id="accompany", reply_text=reply)
        assert "(" not in result.reply_text and "[" not in result.reply_text
        assert "remove_stage_directions" in result.rules_applied


def test_merge_excessive_whitespace(service: ResponsePolicyService) -> None:
    """Test merging of excessive whitespace."""
    reply = "你好。\n\n\n我在这里。   你有什么需要？"
    result = service.apply(mode_id="accompany", reply_text=reply)
    assert "\n\n" not in result.reply_text
    assert "  " not in result.reply_text
    assert "merge_excessive_whitespace" in result.rules_applied


def test_empty_reply_fallback(service: ResponsePolicyService) -> None:
    """Test fallback for empty replies."""
    result = service.apply(mode_id="accompany", reply_text="")
    assert result.reply_text == "我听到了，我们慢慢说。"
    assert "empty_reply_fallback" in result.rules_applied


# ===== Care Mode Tests =====


def test_care_truncate_long_reply(service: ResponsePolicyService) -> None:
    """Test care mode truncates long replies."""
    reply = "这是一个很长的回复。" * 20  # Will be > 120 chars
    result = service.apply(mode_id="care", reply_text=reply)
    assert len(result.reply_text) <= 135  # Allow some buffer for sentence boundary
    assert result.changed
    assert any("truncate" in rule for rule in result.rules_applied)


def test_care_detects_medical_diagnosis(service: ResponsePolicyService) -> None:
    """Test care mode detects and replaces medical diagnosis."""
    test_cases = [
        "你这是抑郁症",
        "你这是双相障碍",
        "你这是焦虑症",
        "你应该吃药",
        "建议服用抗抑郁药",
    ]
    for reply in test_cases:
        result = service.apply(mode_id="care", reply_text=reply)
        assert "我不能替你判断病情" in result.reply_text
        assert "replace_medical_diagnosis" in result.rules_applied


def test_care_adds_safety_for_high_risk_user_text(
    service: ResponsePolicyService,
) -> None:
    """Test care mode adds safety message for high-risk user text."""
    high_risk_cases = [
        "我胸口痛",
        "我呼吸困难",
        "我摔倒了",
        "我想自伤",
    ]
    for user_text in high_risk_cases:
        result = service.apply(
            mode_id="care",
            reply_text="我理解你的感受。",
            user_text=user_text,
        )
        assert "联系家人或医生" in result.reply_text
        assert "add_high_risk_safety_message" in result.rules_applied


def test_care_does_not_duplicate_safety_message(
    service: ResponsePolicyService,
) -> None:
    """Test care mode doesn't duplicate safety message if already present."""
    result = service.apply(
        mode_id="care",
        reply_text="这很危险。请立即联系医生。",
        user_text="我胸口疼",
    )
    # Should only have one mention, not duplicated
    assert result.reply_text.count("医生") == 1


# ===== Accompany Mode Tests =====


def test_accompany_truncate_long_reply(service: ResponsePolicyService) -> None:
    """Test accompany mode truncates long replies."""
    reply = "今天你好吗？" * 30  # Will be > 120 chars
    result = service.apply(mode_id="accompany", reply_text=reply)
    assert len(result.reply_text) <= 135  # Allow some buffer
    assert result.changed


def test_accompany_remove_customer_service_tone(
    service: ResponsePolicyService,
) -> None:
    """Test accompany mode removes customer service phrases."""
    test_cases = [
        "请明确你的需求。",
        "我将为你提供帮助。",
        "请提供更多信息。",
    ]
    for reply in test_cases:
        result = service.apply(mode_id="accompany", reply_text=reply)
        assert "remove_customer_service_tone" in result.rules_applied
        # Should be shorter or different
        assert result.changed


# ===== Learning Mode Tests =====


def test_learning_limit_questions_to_three(service: ResponsePolicyService) -> None:
    """Test learning mode limits self-test questions to 3."""
    reply = "第一个问题？第二个问题？第三个问题？第四个问题？第五个问题？"
    result = service.apply(mode_id="learning", reply_text=reply)
    assert result.reply_text.count("？") <= 3
    assert "limit_to_3_questions" in result.rules_applied


def test_learning_remove_encyclopedic_opening(
    service: ResponsePolicyService,
) -> None:
    """Test learning mode removes encyclopedic openings."""
    test_cases = [
        "这是一个非常复杂的话题。让我为你详细解释。",
        "这涉及多个方面的内容。首先你需要理解。",
    ]
    for reply in test_cases:
        result = service.apply(mode_id="learning", reply_text=reply)
        assert "remove_encyclopedic_opening" in result.rules_applied


def test_learning_longer_char_limit(service: ResponsePolicyService) -> None:
    """Test learning mode has higher character limit (220)."""
    # Create a text that's ~200 chars (should fit)
    reply = "这是一个关于概念的解释。" * 10  # Approximately 160 chars
    result = service.apply(mode_id="learning", reply_text=reply)
    # Should not be truncated much
    assert len(result.reply_text) >= len(reply) * 0.8


def test_learning_truncate_very_long_reply(service: ResponsePolicyService) -> None:
    """Test learning mode truncates very long replies."""
    reply = "这是一个很长的内容。" * 50  # Will be >> 220 chars
    result = service.apply(mode_id="learning", reply_text=reply)
    assert len(result.reply_text) <= 250  # Allow some buffer
    assert result.changed


# ===== Mixed Rules Tests =====


def test_multiple_universal_rules_applied(service: ResponsePolicyService) -> None:
    """Test that multiple universal rules can be applied."""
    reply = """
# 标题
| 表格 | 数据 |
- 项目1
- 项目2

作为一个AI，我可以帮助你。（微笑）


这是内容。
"""
    result = service.apply(mode_id="accompany", reply_text=reply)
    assert len(result.rules_applied) > 1
    assert "#" not in result.reply_text
    assert "|" not in result.reply_text
    assert "AI" not in result.reply_text


def test_result_changed_flag(service: ResponsePolicyService) -> None:
    """Test that changed flag is set correctly."""
    # No changes needed
    result1 = service.apply(mode_id="accompany", reply_text="简单回复。")
    assert result1.changed is False

    # Changes needed
    result2 = service.apply(mode_id="accompany", reply_text="# 标题\n这是内容。")
    assert result2.changed is True


def test_result_char_counts(service: ResponsePolicyService) -> None:
    """Test that character counts are accurate."""
    reply = "你好，我很高兴。" * 10
    result = service.apply(mode_id="care", reply_text=reply)
    assert result.original_chars == len(reply)
    assert result.final_chars == len(result.reply_text)


def test_result_rules_applied_list(service: ResponsePolicyService) -> None:
    """Test that rules_applied list contains applied rules."""
    reply = "# 标题\n（点头）你好。"
    result = service.apply(mode_id="accompany", reply_text=reply)
    assert isinstance(result.rules_applied, list)
    assert len(result.rules_applied) > 0
    assert all(isinstance(r, str) for r in result.rules_applied)


# ===== Edge Cases =====


def test_whitespace_only_reply(service: ResponsePolicyService) -> None:
    """Test handling of whitespace-only replies."""
    result = service.apply(mode_id="accompany", reply_text="   \n\n   ")
    assert result.reply_text == "我听到了，我们慢慢说。"


def test_very_short_reply(service: ResponsePolicyService) -> None:
    """Test handling of very short replies."""
    result = service.apply(mode_id="accompany", reply_text="嗯。")
    assert len(result.reply_text) > 0
    assert "嗯" in result.reply_text


def test_special_characters_preserved(service: ResponsePolicyService) -> None:
    """Test that special characters are preserved where appropriate."""
    reply = "是吗？太好了！"
    result = service.apply(mode_id="accompany", reply_text=reply)
    assert "？" in result.reply_text
    assert "！" in result.reply_text


def test_mode_case_insensitive_not_required(service: ResponsePolicyService) -> None:
    """Test that mode_id is case-sensitive (as expected)."""
    # Game mode should not apply care/accompany/learning rules
    result = service.apply(mode_id="game", reply_text="你这是抑郁症。")
    # Game mode has no special rules, so medical diagnosis won't be replaced
    assert "你这是抑郁症" in result.reply_text
