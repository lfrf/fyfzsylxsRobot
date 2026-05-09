from __future__ import annotations

from logging_utils import log_event

from .schemas import CareStrategy


class CareStrategyPlanner:
    """Rule-based care strategy planner before LLM generation."""

    HIGH_RISK = ("自伤", "自杀", "胸痛", "胸口痛", "呼吸困难", "摔倒", "晕倒", "意识模糊", "割腕", "120")

    STRATEGY_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
        ("relief_closure", ("好多了", "好点了", "放松了", "谢谢", "没事了", "舒服多了")),
        ("tired_support", ("累", "困", "疲惫", "没精神", "睡不好", "乏")),
        ("sad_validation", ("难过", "委屈", "低落", "伤心", "想哭", "不开心")),
        ("anxiety_grounding", ("焦虑", "担心", "紧张", "害怕", "慌", "压力")),
        ("anger_deescalation", ("烦", "崩溃", "火大", "生气", "气死", "受不了")),
        ("loneliness_company", ("孤独", "无聊", "没人陪", "一个人", "寂寞")),
        ("quiet_presence", ("不想说话", "想安静", "别问", "先别说", "沉默")),
    )

    STRATEGIES: dict[str, CareStrategy] = {
        "tired_support": CareStrategy(
            strategy_id="tired_support",
            emotion_label="tired",
            reply_goal="承认疲惫和消耗，降低任务压力，给一个低成本恢复动作。",
            preferred_structure="具体疲惫镜像 -> 降低压力 -> 一个轻动作或轻问题",
            avoid_default_phrases=["喝点水休息一下", "慢慢说", "我在这里陪你"],
        ),
        "sad_validation": CareStrategy(
            strategy_id="sad_validation",
            emotion_label="sad",
            reply_goal="接住难过或委屈，不急着讲道理。",
            preferred_structure="命名情绪 -> 允许低落 -> 轻问一句发生了什么",
            avoid_default_phrases=["别难过", "想开一点", "我在这里陪你"],
        ),
        "anxiety_grounding": CareStrategy(
            strategy_id="anxiety_grounding",
            emotion_label="anxious",
            reply_goal="稳定节奏，把问题缩小到眼前可处理的一步。",
            preferred_structure="承认紧张 -> 缩小问题 -> 先做一个小步骤",
            avoid_default_phrases=["不要担心", "慢慢说", "放轻松"],
        ),
        "anger_deescalation": CareStrategy(
            strategy_id="anger_deescalation",
            emotion_label="angry",
            reply_goal="承认烦躁，不评判，不火上浇油。",
            preferred_structure="承认烦躁 -> 给出空间 -> 询问是否要说具体原因",
            avoid_default_phrases=["别生气", "冷静点", "我在这里陪你"],
        ),
        "loneliness_company": CareStrategy(
            strategy_id="loneliness_company",
            emotion_label="lonely",
            reply_goal="提供陪伴感，但避免反复模板化承诺。",
            preferred_structure="接住孤独 -> 给短陪伴回应 -> 开一个轻话题",
            avoid_default_phrases=["我在这里陪你", "你并不孤单", "慢慢说"],
        ),
        "quiet_presence": CareStrategy(
            strategy_id="quiet_presence",
            emotion_label="quiet",
            reply_goal="低输出陪伴，尊重用户不想说话。",
            preferred_structure="尊重安静 -> 低压力存在 -> 不追问",
            avoid_default_phrases=["你愿意说说吗", "慢慢说", "发生了什么"],
        ),
        "relief_closure": CareStrategy(
            strategy_id="relief_closure",
            emotion_label="relieved",
            reply_goal="肯定状态变好，轻轻收束，不继续追问压力。",
            preferred_structure="肯定变化 -> 保留轻松感 -> 简短收束",
            avoid_default_phrases=["继续说说", "还有哪里不舒服", "我在这里陪你"],
        ),
        "safety_escalation": CareStrategy(
            strategy_id="safety_escalation",
            emotion_label="risk",
            risk_level="high",
            reply_goal="优先安全提醒，建议联系家人、医生或紧急服务，不做诊断。",
            preferred_structure="明确安全优先 -> 建议立即联系现实支持 -> 不做诊断",
            avoid_default_phrases=["忍一忍", "休息一下就好", "没事的"],
        ),
        "general_support": CareStrategy(),
    }

    def plan(
        self,
        asr_text: str | None,
        recent_strategy_ids: list[str] | None = None,
        recent_reply_texts: list[str] | None = None,
    ) -> CareStrategy:
        text = str(asr_text or "")
        recent_strategy_ids = recent_strategy_ids or []
        recent_reply_texts = recent_reply_texts or []

        if any(keyword in text for keyword in self.HIGH_RISK):
            strategy = self.STRATEGIES["safety_escalation"]
        else:
            strategy = self.STRATEGIES["general_support"]
            for strategy_id, keywords in self.STRATEGY_KEYWORDS:
                if any(keyword in text for keyword in keywords):
                    strategy = self.STRATEGIES[strategy_id]
                    break

        strategy = self._with_variant(strategy, recent_strategy_ids)
        log_event(
            "care_strategy_planned",
            strategy_id=strategy.strategy_id,
            emotion_label=strategy.emotion_label,
            risk_level=strategy.risk_level,
            approach_variant=strategy.approach_variant,
            recent_strategy_ids=recent_strategy_ids[-5:],
            recent_reply_count=len(recent_reply_texts),
        )
        return strategy

    def _with_variant(self, strategy: CareStrategy, recent_strategy_ids: list[str]) -> CareStrategy:
        repeated_count = 0
        for item in reversed(recent_strategy_ids):
            if item == strategy.strategy_id:
                repeated_count += 1
            else:
                break
        if repeated_count == 0:
            variant = "default"
        elif repeated_count == 1:
            variant = "shift_approach"
        else:
            variant = "quiet_or_concrete"
        return CareStrategy(
            strategy_id=strategy.strategy_id,
            emotion_label=strategy.emotion_label,
            risk_level=strategy.risk_level,
            reply_goal=strategy.reply_goal,
            preferred_structure=strategy.preferred_structure,
            avoid_default_phrases=list(strategy.avoid_default_phrases),
            approach_variant=variant,
        )


care_strategy_planner = CareStrategyPlanner()
