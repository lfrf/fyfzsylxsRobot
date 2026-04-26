from models import AvatarAction, ChatRequest


class PolicyService:
    def select_emotion_style(self, request: ChatRequest, transcript: str) -> str:
        lowered = transcript.lower()
        speech_tags = {tag.lower() for tag in (request.speech_features.emotion_tags if request.speech_features else [])}
        if request.input_type == "audio" and {"hesitant", "fatigued", "agitated"} & speech_tags:
            return "gentle"
        if request.input_type == "audio" and "energized" in speech_tags:
            return "attentive"
        if request.input_type == "audio":
            return "listening"
        if any(keyword in lowered for keyword in ["sad", "unhappy", "压力", "焦虑", "难过", "不开心"]):
            return "gentle"
        return "supportive"

    def select_avatar_action(self, request: ChatRequest, transcript: str) -> AvatarAction:
        lowered = transcript.lower()
        speech_tags = {tag.lower() for tag in (request.speech_features.emotion_tags if request.speech_features else [])}
        if request.input_type == "audio" and {"hesitant", "fatigued"} & speech_tags:
            return AvatarAction(
                facial_expression="soft_concern",
                head_motion="slow_nod",
            )
        if request.input_type == "audio" and "energized" in speech_tags:
            return AvatarAction(
                facial_expression="attentive",
                head_motion="steady",
            )
        if request.input_type == "audio":
            return AvatarAction(
                facial_expression="attentive",
                head_motion="slow_nod",
            )
        if any(keyword in lowered for keyword in ["sad", "unhappy", "压力", "焦虑", "难过", "不开心"]):
            return AvatarAction(
                facial_expression="soft_concern",
                head_motion="slow_nod",
            )
        return AvatarAction(
            facial_expression="neutral_smile",
            head_motion="steady",
        )
policy_service = PolicyService()
