from services.output_control.care_strategy_planner import CareStrategyPlanner
from services.output_control.memory_quality_classifier import MemoryQualityClassifier
from services.output_control.rag_context_controller import RAGContextController
from services.output_control.reply_history_tracker import ReplyHistoryTracker


def test_care_strategy_planner_detects_core_strategies() -> None:
    planner = CareStrategyPlanner()

    assert planner.plan("我今天有点累").strategy_id == "tired_support"
    assert planner.plan("我有点焦虑").strategy_id == "anxiety_grounding"
    assert planner.plan("我现在好多了，谢谢你").strategy_id == "relief_closure"
    assert planner.plan("我不想说话").strategy_id == "quiet_presence"
    assert planner.plan("我胸口痛，呼吸困难").strategy_id == "safety_escalation"


def test_reply_history_tracks_repetition_and_avoid_phrases() -> None:
    tracker = ReplyHistoryTracker(history_size=3)
    tracker.record("s1", "care", "tired_support", "我在这里陪你，慢慢说。")
    tracker.record("s1", "care", "tired_support", "先喝点水，休息一下。")
    tracker.record("s1", "care", "sad_validation", "这确实不好受。")

    assert tracker.get_recent_strategy_ids("s1") == ["tired_support", "tired_support", "sad_validation"]
    avoid = tracker.get_avoid_phrases("s1")
    assert "我在这里陪你" in avoid
    assert "喝点水" in avoid


def test_memory_quality_filters_noise_and_classifies_profile_signals() -> None:
    classifier = MemoryQualityClassifier()

    assert classifier.classify("嗯").should_write_memory is False
    assert classifier.classify("测试一下你能听见我吗").memory_type == "noise"
    assert classifier.classify("我叫小周").memory_type == "identity"
    assert classifier.classify("我喜欢简洁回答").memory_type == "preference"
    assert classifier.classify("我最近在准备嵌入式系统考试，担心 UART 和 ADC").memory_type == "learning_goal"
    assert classifier.classify("我今天很累").memory_type == "emotional_state"


def test_rag_context_controller_compresses_care_context() -> None:
    controller = RAGContextController()
    context = "【来源：x.md】\n用户疲惫时先降低压力，不要催促。可以给一个低成本恢复动作。\n\n---\n\n不要做医疗诊断。"

    guidance = controller.compress("care", context, strategy_id="tired_support", max_chars=180)

    assert guidance is not None
    assert guidance.startswith("Care guidance:")
    assert len(guidance) <= 180
    assert "tired_support" in guidance
