"""ResponsePolicyService: post-process LLM output to fit robot TTS and mode requirements."""

from __future__ import annotations

import re
from dataclasses import dataclass
from logging_utils import log_event


@dataclass(frozen=True)
class ResponsePolicyResult:
    """Result of response policy processing."""

    reply_text: str
    changed: bool
    rules_applied: list[str]
    original_chars: int
    final_chars: int


class ResponsePolicyService:
    """Post-process LLM replies to ensure they fit TTS constraints and mode requirements."""

    # Default fallback for empty replies
    DEFAULT_FALLBACK = "我听到了，我们慢慢说。"

    # Character limits per mode
    CHAR_LIMITS = {
        "care": 120,
        "accompany": 120,
        "learning": 220,
        "game": 150,
    }

    # High-risk keywords that require mentioning family/doctor
    HIGH_RISK_KEYWORDS = {
        "胸口痛",
        "胸口疼",
        "胸痛",
        "呼吸困难",
        "呼吸不畅",
        "摔倒",
        "自伤",
        "自杀",
        "割腕",
        "头晕严重",
        "晕倒",
        "意识模糊",
    }

    def apply(
        self,
        *,
        mode_id: str,
        reply_text: str,
        user_text: str | None = None,
    ) -> ResponsePolicyResult:
        """Apply response policy rules to LLM output."""
        if not reply_text:
            return ResponsePolicyResult(
                reply_text=self.DEFAULT_FALLBACK,
                changed=True,
                rules_applied=["empty_reply_fallback"],
                original_chars=0,
                final_chars=len(self.DEFAULT_FALLBACK),
            )

        original_text = reply_text
        original_chars = len(original_text)
        rules_applied: list[str] = []

        # Apply universal rules
        reply_text, applied = self._apply_universal_rules(reply_text)
        rules_applied.extend(applied)

        # Apply mode-specific rules
        if mode_id == "care":
            reply_text, applied = self._apply_care_rules(reply_text, user_text)
            rules_applied.extend(applied)
        elif mode_id == "accompany":
            reply_text, applied = self._apply_accompany_rules(reply_text)
            rules_applied.extend(applied)
        elif mode_id == "learning":
            reply_text, applied = self._apply_learning_rules(reply_text)
            rules_applied.extend(applied)

        # Final safety check: don't let it be empty
        if not reply_text.strip():
            reply_text = self.DEFAULT_FALLBACK
            rules_applied.append("empty_after_processing_fallback")

        final_chars = len(reply_text)
        changed = original_text != reply_text

        self._log_applied(
            mode=mode_id,
            original_chars=original_chars,
            final_chars=final_chars,
            changed=changed,
            rules_applied=rules_applied,
        )

        return ResponsePolicyResult(
            reply_text=reply_text,
            changed=changed,
            rules_applied=rules_applied,
            original_chars=original_chars,
            final_chars=final_chars,
        )

    def _apply_universal_rules(self, text: str) -> tuple[str, list[str]]:
        """Apply rules that apply to all modes."""
        rules: list[str] = []

        # 1. Remove markdown headings (# ## ### etc)
        if "#" in text:
            text = re.sub(r"^#+\s*", "", text, flags=re.MULTILINE)
            rules.append("remove_markdown_headings")

        # 2. Remove table symbols
        if "|" in text:
            text = text.replace("|", "")
            rules.append("remove_table_symbols")

        # 3. Remove bullet points and list symbols
        original = text
        text = re.sub(r"^\s*[-*]\s+", "", text, flags=re.MULTILINE)
        text = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.MULTILINE)
        if original != text:
            rules.append("remove_list_symbols")

        # 4. Remove "作为AI" phrases
        original = text
        text = re.sub(r"作为一个\s*AI[语言模型]*[，。]?", "", text)
        text = re.sub(r"作为\s*AI\s*[语言模型]*[，。]?", "", text)
        text = re.sub(r"我是一个\s*AI[，。]?", "", text)
        if original != text:
            rules.append("remove_ai_self_reference")

        # 5. Remove stage directions like (点头) [微笑] 等
        original = text
        text = re.sub(r"[\(（].*?[\)）]", "", text)  # Remove (...)
        text = re.sub(r"[\[【].*?[\]】]", "", text)  # Remove [...] and 【...】
        if original != text:
            rules.append("remove_stage_directions")

        # 6. Merge excessive whitespace
        original = text
        text = re.sub(r"\n\n+", "\n", text)  # Multiple newlines to single
        text = re.sub(r"  +", " ", text)  # Multiple spaces to single
        text = text.strip()
        if original != text:
            rules.append("merge_excessive_whitespace")

        return text, rules

    def _apply_care_rules(
        self, text: str, user_text: str | None = None
    ) -> tuple[str, list[str]]:
        """Apply care mode rules."""
        rules: list[str] = []
        char_limit = self.CHAR_LIMITS["care"]

        # 1. Check for medical diagnosis phrases
        if self._contains_medical_diagnosis(text):
            text = (
                "我不能替你判断病情。如果一直不舒服，"
                "建议联系家人或医生。"
            )
            rules.append("replace_medical_diagnosis")
        else:
            # 2. Check for length and truncate if needed
            if len(text) > char_limit:
                text = self._truncate_by_sentence(text, char_limit)
                rules.append(f"truncate_to_{char_limit}_chars")

            # 3. If user text contains high-risk keywords, ensure mention family/doctor
            if user_text and self._contains_high_risk_keywords(user_text):
                if not self._contains_family_doctor_mention(text):
                    # Append safety message
                    text = f"{text} 如果一直不舒服或加重，请立即联系家人或医生。"
                    rules.append("add_high_risk_safety_message")

        return text, rules

    def _apply_accompany_rules(self, text: str) -> tuple[str, list[str]]:
        """Apply accompany mode rules."""
        rules: list[str] = []
        char_limit = self.CHAR_LIMITS["accompany"]

        # 1. Remove customer service tone phrases
        original = text
        text = re.sub(r"请明确你的需求[，。]?", "", text)
        text = re.sub(r"请明确.*?需求[，。]?", "", text)
        text = re.sub(r"我将为你提供帮助[，。]?", "", text)
        text = re.sub(r"请提供更多信息[，。]?", "", text)
        text = re.sub(r"请告诉我.*?[，。]?", "你", text)  # Simplify demands
        if original != text:
            rules.append("remove_customer_service_tone")

        # 2. Limit length
        if len(text) > char_limit:
            text = self._truncate_by_sentence(text, char_limit)
            rules.append(f"truncate_to_{char_limit}_chars")

        return text, rules

    def _apply_learning_rules(self, text: str) -> tuple[str, list[str]]:
        """Apply learning mode rules."""
        rules: list[str] = []
        char_limit = self.CHAR_LIMITS["learning"]

        # 1. Remove encyclopedic openings
        original = text
        text = re.sub(
            r"这是一个非常复杂.*?话题[，。]?",
            "",
            text,
        )
        text = re.sub(
            r"这涉及.*?方面[，。]?",
            "",
            text,
        )
        if original != text:
            rules.append("remove_encyclopedic_opening")

        # 2. Limit to max 3 self-test questions
        if self._count_questions(text) > 3:
            text = self._keep_only_n_questions(text, 3)
            rules.append("limit_to_3_questions")

        # 3. Limit length
        if len(text) > char_limit:
            text = self._truncate_by_sentence(text, char_limit)
            rules.append(f"truncate_to_{char_limit}_chars")

        return text, rules

    # Helper methods

    def _contains_medical_diagnosis(self, text: str) -> bool:
        """Detect medical diagnosis claims."""
        patterns = [
            r"你这是.*?(抑郁症|双相障碍|焦虑症|躁郁症)",
            r"你可能有.*?(抑郁症|双相障碍|焦虑症)",
            r"你应该吃",
            r"建议服用",
            r"处方",
        ]
        for pattern in patterns:
            if re.search(pattern, text):
                return True
        return False

    def _contains_high_risk_keywords(self, text: str) -> bool:
        """Check if user text contains high-risk keywords."""
        return any(kw in text for kw in self.HIGH_RISK_KEYWORDS)

    def _contains_family_doctor_mention(self, text: str) -> bool:
        """Check if reply already mentions family or doctor."""
        patterns = [
            r"联系家人",
            r"联系医生",
            r"及时寻求帮助",
            r"立即.*?医生",
            r"紧急服务",
            r"120",
        ]
        for pattern in patterns:
            if re.search(pattern, text):
                return True
        return False

    def _truncate_by_sentence(self, text: str, max_chars: int) -> str:
        """Truncate text by sentence boundary, not mid-word."""
        if len(text) <= max_chars:
            return text

        # Try to truncate at sentence boundary
        sentences = re.split(r"[。！？；]", text)
        result = ""

        for sentence in sentences:
            if len(result) + len(sentence) + 1 <= max_chars:
                result += sentence + "。" if result else sentence
            else:
                break

        # If we got nothing, hard truncate
        if not result:
            result = text[:max_chars]

        return result.rstrip("。") if result.endswith("。") else result

    def _count_questions(self, text: str) -> int:
        """Count question marks in text."""
        return text.count("？") + text.count("?")

    def _keep_only_n_questions(self, text: str, n: int) -> str:
        """Keep only first n questions."""
        questions_found = 0
        result = []

        for char in text:
            if char in "？?":
                questions_found += 1
                if questions_found <= n:
                    result.append(char)
            else:
                if questions_found <= n:
                    result.append(char)

        return "".join(result).strip()

    def _log_applied(
        self,
        *,
        mode: str,
        original_chars: int,
        final_chars: int,
        changed: bool,
        rules_applied: list[str],
    ) -> None:
        """Log response policy application."""
        log_event(
            "response_policy_applied",
            mode=mode,
            original_chars=original_chars,
            final_chars=final_chars,
            changed=changed,
            rules_applied_count=len(rules_applied),
            rules_applied=",".join(rules_applied),
        )


# Singleton instance
response_policy_service = ResponsePolicyService()

__all__ = ["ResponsePolicyService", "ResponsePolicyResult", "response_policy_service"]
