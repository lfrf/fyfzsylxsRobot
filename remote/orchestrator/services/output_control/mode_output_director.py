from __future__ import annotations

from typing import Any

from config import settings
from logging_utils import log_event

from .care_strategy_planner import care_strategy_planner
from .rag_context_controller import rag_context_controller
from .reply_history_tracker import reply_history_tracker
from .schemas import OutputControlPlan


class ModeOutputDirector:
    """Builds pre-LLM guidance for mode-specific output quality."""

    def plan(
        self,
        *,
        mode_id: str,
        session_id: str,
        turn_id: str,
        asr_text: str,
        rag_context: str | None = None,
        profile_context: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> OutputControlPlan:
        metadata = metadata or {}
        if not settings.output_control_enabled:
            return OutputControlPlan(
                mode_id=mode_id,
                rag_guidance=rag_context,
                profile_context=profile_context,
                debug={"enabled": False},
            )

        if mode_id == "care" and settings.care_strategy_enabled:
            recent_strategy_ids = reply_history_tracker.get_recent_strategy_ids(session_id)
            recent_reply_texts = reply_history_tracker.get_recent_reply_texts(session_id)
            strategy = care_strategy_planner.plan(
                asr_text,
                recent_strategy_ids=recent_strategy_ids,
                recent_reply_texts=recent_reply_texts,
            )
            avoid_phrases = self._dedupe(strategy.avoid_default_phrases + reply_history_tracker.get_avoid_phrases(session_id))
            rag_guidance = rag_context_controller.compress(
                mode_id,
                rag_context,
                strategy_id=strategy.strategy_id,
                max_chars=settings.care_rag_max_chars,
            )
            plan = OutputControlPlan(
                mode_id=mode_id,
                strategy_id=strategy.strategy_id,
                emotion_label=strategy.emotion_label,
                risk_level=strategy.risk_level,
                reply_goal=strategy.reply_goal,
                prompt_hints=[
                    f"structure: {strategy.preferred_structure}",
                    f"approach_variant: {strategy.approach_variant}",
                    "回复要像口语，不要列表，不要解释策略本身。",
                ],
                avoid_phrases=avoid_phrases,
                avoid_strategy_ids=recent_strategy_ids[-2:] if recent_strategy_ids[-2:].count(strategy.strategy_id) >= 2 else [],
                rag_guidance=rag_guidance,
                profile_context=profile_context,
                debug={
                    "enabled": True,
                    "mode_id": mode_id,
                    "strategy_id": strategy.strategy_id,
                    "emotion_label": strategy.emotion_label,
                    "risk_level": strategy.risk_level,
                    "avoid_phrases": avoid_phrases,
                    "rag_original_chars": len(rag_context or ""),
                    "rag_final_chars": len(rag_guidance or ""),
                    "profile_context_chars": len(profile_context or ""),
                },
            )
            self._log(plan, session_id=session_id, turn_id=turn_id)
            return plan

        prompt_hints = {
            "accompany": ["接话 -> 轻延展 -> 自然反问，像桌面伙伴，不像客服。"],
            "learning": ["判断问题 -> 2-3步解释 -> 一个下一步，保留关键术语。"],
            "game": ["维护当前游戏状态 -> 一步推进 -> 等待用户回应。"],
        }.get(mode_id, [])
        plan = OutputControlPlan(
            mode_id=mode_id,
            prompt_hints=prompt_hints,
            rag_guidance=rag_context_controller.compress(mode_id, rag_context),
            profile_context=profile_context,
            debug={
                "enabled": True,
                "mode_id": mode_id,
                "strategy_id": None,
                "rag_original_chars": len(rag_context or ""),
                "rag_final_chars": len(rag_context or ""),
                "profile_context_chars": len(profile_context or ""),
            },
        )
        self._log(plan, session_id=session_id, turn_id=turn_id)
        return plan

    def _log(self, plan: OutputControlPlan, *, session_id: str, turn_id: str) -> None:
        log_event(
            "output_control_plan_built",
            session_id=session_id,
            turn_id=turn_id,
            mode_id=plan.mode_id,
            strategy_id=plan.strategy_id,
            risk_level=plan.risk_level,
            avoid_phrase_count=len(plan.avoid_phrases),
            rag_final_chars=len(plan.rag_guidance or ""),
        )

    def _dedupe(self, items: list[str]) -> list[str]:
        result = []
        for item in items:
            text = str(item or "").strip()
            if text and text not in result:
                result.append(text)
        return result


mode_output_director = ModeOutputDirector()
