from contracts.schemas import (
    EmotionResult,
    ModeSwitchResult,
    RobotChatRequest,
    RobotChatResponse,
)

from services.mode_manager import ModeManager, mode_manager
from services.mode_policy import get_mode_policy
from services.rag_router import RagRouter, rag_router
from services.robot_action_service import RobotActionService, robot_action_service
from services.tts_service import RobotTTSService, robot_tts_service


class RobotChatService:
    def __init__(
        self,
        *,
        modes: ModeManager | None = None,
        rag: RagRouter | None = None,
        tts: RobotTTSService | None = None,
        actions: RobotActionService | None = None,
    ) -> None:
        self.modes = modes or mode_manager
        self.rag = rag or rag_router
        self.tts = tts or robot_tts_service
        self.actions = actions or robot_action_service

    def handle_chat_turn(self, request: RobotChatRequest) -> RobotChatResponse:
        asr_text = self._asr_stub(request)
        current_mode = self.modes.get_session_mode(request.session_id, request.mode)
        switch = self.modes.detect_switch(asr_text)

        if switch.detected and switch.target_mode:
            target_mode = self.modes.set_session_mode(request.session_id, switch.target_mode)
            policy = get_mode_policy(target_mode)
            rag_route = self.rag.route_for_mode(policy)
            reply_text = policy.confirmation_text
            emotion = EmotionResult(label="neutral", confidence=1.0)
            robot_action = self.actions.for_mode_switch(policy)
            tts_result = self.tts.synthesize(
                text=reply_text,
                session_id=request.session_id,
                turn_id=request.turn_id,
            )
            return RobotChatResponse(
                success=True,
                session_id=request.session_id,
                turn_id=request.turn_id,
                mode=policy.to_mode_info(),
                mode_switch=ModeSwitchResult(
                    switched=True,
                    from_mode=current_mode,
                    to_mode=target_mode,
                    reason=f"matched command: {switch.matched_text}",
                    confirmation_text=reply_text,
                ),
                mode_changed=True,
                active_rag_namespace=rag_route.namespace,
                asr_text=asr_text,
                reply_text=reply_text,
                emotion=emotion,
                tts=tts_result,
                robot_action=robot_action,
                debug={
                    "source": "robot_chat_service",
                    "rag_route_source": rag_route.source,
                    "full_llm_rag_tts": "stubbed",
                },
            )

        policy = get_mode_policy(current_mode)
        rag_route = self.rag.route_for_mode(policy)
        emotion = self._emotion_stub(asr_text)
        reply_text = self._reply_stub(policy.mode_id, asr_text)
        robot_action = self.actions.for_chat(policy, emotion)
        tts_result = self.tts.synthesize(
            text=reply_text,
            session_id=request.session_id,
            turn_id=request.turn_id,
        )
        return RobotChatResponse(
            success=True,
            session_id=request.session_id,
            turn_id=request.turn_id,
            mode=policy.to_mode_info(),
            mode_switch=ModeSwitchResult(
                switched=False,
                from_mode=current_mode,
                to_mode=current_mode,
            ),
            mode_changed=False,
            active_rag_namespace=rag_route.namespace,
            asr_text=asr_text,
            reply_text=reply_text,
            emotion=emotion,
            tts=tts_result,
            robot_action=robot_action,
            debug={
                "source": "robot_chat_service",
                "rag_route_source": rag_route.source,
                "full_llm_rag_tts": "stubbed",
            },
        )

    def _asr_stub(self, request: RobotChatRequest) -> str:
        if request.input.text_hint and request.input.text_hint.strip():
            return request.input.text_hint.strip()
        return "mock audio received"

    def _emotion_stub(self, asr_text: str) -> EmotionResult:
        if any(token in asr_text for token in ("累", "困", "疲惫")):
            return EmotionResult(label="tired", confidence=0.65, valence="negative", arousal="low")
        if any(token in asr_text for token in ("开心", "高兴", "太好了")):
            return EmotionResult(label="happy", confidence=0.65, valence="positive", arousal="medium")
        return EmotionResult(label="neutral", confidence=0.5)

    def _reply_stub(self, mode_id: str, asr_text: str) -> str:
        policy = get_mode_policy(mode_id)
        if asr_text == "mock audio received":
            return policy.normal_reply
        return f"{policy.normal_reply} 你刚才说的是：{asr_text}"


robot_chat_service = RobotChatService()

__all__ = ["RobotChatService", "robot_chat_service"]
