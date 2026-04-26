from dataclasses import dataclass

from contracts.schemas import ModeInfo


@dataclass(frozen=True)
class ModePolicy:
    mode_id: str
    display_name: str
    prompt_policy: str
    rag_namespace: str
    action_style: str
    speech_style: str
    confirmation_text: str
    normal_reply: str
    switch_expression: str
    switch_motion: str

    def to_mode_info(self) -> ModeInfo:
        return ModeInfo(
            mode_id=self.mode_id,
            display_name=self.display_name,
            prompt_policy=self.prompt_policy,
            rag_namespace=self.rag_namespace,
            action_style=self.action_style,
        )


MODE_POLICIES = {
    "elderly": ModePolicy(
        mode_id="elderly",
        display_name="老年模式",
        prompt_policy="elderly_gentle",
        rag_namespace="elderly_care",
        action_style="calm_supportive",
        speech_style="elderly_gentle",
        confirmation_text="好的，已切换为老年模式。我会说得慢一点、清楚一点，也会更温和地陪你。",
        normal_reply="我听到了。我会用温和一点的方式陪你，我们慢慢说。",
        switch_expression="comfort",
        switch_motion="slow_nod",
    ),
    "child": ModePolicy(
        mode_id="child",
        display_name="儿童模式",
        prompt_policy="child_playful",
        rag_namespace="child_companion",
        action_style="playful_warm",
        speech_style="child_playful",
        confirmation_text="好呀，已经切换为儿童模式。我会用更简单、有趣的话和你聊天。",
        normal_reply="我听到啦，我们可以轻松地聊一聊。",
        switch_expression="happy",
        switch_motion="happy_nod",
    ),
    "student": ModePolicy(
        mode_id="student",
        display_name="学生模式",
        prompt_policy="student_focused",
        rag_namespace="student_learning",
        action_style="focused_encouraging",
        speech_style="student_focused",
        confirmation_text="好的，已切换为学生模式。我会更有条理地帮你分析和学习。",
        normal_reply="收到，我们可以一步一步把问题理清楚。",
        switch_expression="listening",
        switch_motion="center",
    ),
    "normal": ModePolicy(
        mode_id="normal",
        display_name="普通模式",
        prompt_policy="normal",
        rag_namespace="general",
        action_style="neutral_warm",
        speech_style="normal",
        confirmation_text="好的，已切换为普通模式。我们可以自然地继续聊天。",
        normal_reply="我听到了，我们继续聊。",
        switch_expression="neutral",
        switch_motion="center",
    ),
}

DEFAULT_MODE_ID = "elderly"


def normalize_mode(mode_id: str | None) -> str:
    if mode_id in MODE_POLICIES:
        return mode_id
    return DEFAULT_MODE_ID


def get_mode_policy(mode_id: str | None) -> ModePolicy:
    return MODE_POLICIES[normalize_mode(mode_id)]
