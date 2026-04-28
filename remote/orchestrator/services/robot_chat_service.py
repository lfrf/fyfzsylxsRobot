from contracts.schemas import (
    EmotionResult,
    ModeSwitchResult,
    RobotChatRequest,
    RobotChatResponse,
)

from clients.asr_client import ASRClient, asr_client
from clients.llm_client import LLMClient, llm_client
from clients.rag_client import RAGClient, rag_client
from clients.tts_client import TTSClient, tts_client
from services.mode_manager import ModeManager, mode_manager
from services.mode_policy import get_mode_policy
from services.rag_router import RagRouter, rag_router
from services.robot_action_service import RobotActionService, robot_action_service


class RobotChatService:
    def __init__(
        self,
        *,
        modes: ModeManager | None = None,
        rag: RagRouter | None = None,
        asr: ASRClient | None = None,
        llm: LLMClient | None = None,
        tts: TTSClient | None = None,
        rag_client_instance: RAGClient | None = None,
        actions: RobotActionService | None = None,
    ) -> None:
        self.modes = modes or mode_manager
        self.rag = rag or rag_router
        self.asr = asr or asr_client
        self.llm = llm or llm_client
        self.tts = tts or tts_client
        self.rag_client = rag_client_instance or rag_client
        self.actions = actions or robot_action_service

    def handle_chat_turn(self, request: RobotChatRequest) -> RobotChatResponse:
        asr_result = self.asr.transcribe(request)
        asr_text = asr_result.text
        current_mode = self.modes.get_session_mode(request.session_id, request.mode)
        switch = self.modes.detect_switch(asr_text)

        if switch.detected and switch.target_mode:
            target_mode = self.modes.set_session_mode(request.session_id, switch.target_mode)
            policy = get_mode_policy(target_mode)
            rag_route = self.rag.route_for_mode(policy)
            reply_text = policy.confirmation_text
            emotion = EmotionResult(label="neutral", confidence=1.0)
            robot_action = self.actions.for_mode_switch(policy)
            tts_client_result = self.tts.synthesize(
                text=reply_text,
                session_id=request.session_id,
                turn_id=request.turn_id,
                mode=policy.mode_id,
                speech_style=policy.speech_style,
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
                tts=tts_client_result.tts,
                robot_action=robot_action,
                debug={
                    "source": "robot_chat_service",
                    "asr_source": asr_result.source,
                    "rag_route_source": rag_route.source,
                    "tts_source": tts_client_result.source,
                    "llm_skipped": "mode_switch",
                },
            )

        policy = get_mode_policy(current_mode)
        rag_route = self.rag.route_for_mode(policy)
        rag_context = self.rag_client.retrieve_context(namespace=rag_route.namespace, query=asr_text)
        emotion = self._emotion_stub(asr_text)
        llm_result = self.llm.generate_reply(
            session_id=request.session_id,
            turn_id=request.turn_id,
            asr_text=asr_text,
            mode_policy=policy,
            rag_route=rag_route,
            rag_context=rag_context,
        )
        reply_text = llm_result.reply_text
        robot_action = self.actions.for_chat(policy, emotion)
        tts_client_result = self.tts.synthesize(
            text=reply_text,
            session_id=request.session_id,
            turn_id=request.turn_id,
            mode=policy.mode_id,
            speech_style=policy.speech_style,
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
            tts=tts_client_result.tts,
            robot_action=robot_action,
            debug={
                "source": "robot_chat_service",
                "asr_source": asr_result.source,
                "llm_source": llm_result.source,
                "llm_reasoning_hint": llm_result.reasoning_hint,
                "rag_route_source": rag_route.source,
                "rag_context_used": bool(rag_context),
                "tts_source": tts_client_result.source,
            },
        )

    def _emotion_stub(self, asr_text: str) -> EmotionResult:
        if any(token in asr_text for token in ("累", "困", "疲惫")):
            return EmotionResult(label="tired", confidence=0.65, valence="negative", arousal="low")
        if any(token in asr_text for token in ("开心", "高兴", "太好了")):
            return EmotionResult(label="happy", confidence=0.65, valence="positive", arousal="medium")
        return EmotionResult(label="neutral", confidence=0.5)


robot_chat_service = RobotChatService()

__all__ = ["RobotChatService", "robot_chat_service"]
