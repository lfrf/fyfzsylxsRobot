from time import perf_counter
from uuid import uuid4

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
from logging_utils import log_event
from services.mode_manager import ModeManager, mode_manager
from services.mode_policy import get_mode_service
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
        trace_id = uuid4().hex
        total_started = perf_counter()
        log_event(
            "robot_chat_request_received",
            trace_id=trace_id,
            session_id=request.session_id,
            turn_id=request.turn_id,
            mode=request.mode,
            has_audio_base64=bool(request.input.audio_base64),
            audio_base64_len=len(request.input.audio_base64 or ""),
            has_text_hint=bool(request.input.text_hint and request.input.text_hint.strip()),
            sample_rate=request.input.sample_rate,
            channels=request.input.channels,
        )
        asr_result = self.asr.transcribe(request)
        asr_text = asr_result.text
        current_mode = self.modes.get_session_mode(request.session_id, request.mode)
        switch = self.modes.detect_switch(asr_text)

        if switch.detected and switch.target_mode:
            target_mode = self.modes.set_session_mode(request.session_id, switch.target_mode)
            policy = get_mode_service(target_mode).get_policy()
            rag_route = self.rag.route_for_mode(policy)
            log_event(
                "mode_switch_detected",
                trace_id=trace_id,
                from_mode=current_mode,
                to_mode=target_mode,
                matched_text=switch.matched_text,
                active_rag_namespace=rag_route.namespace,
            )
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
            response = RobotChatResponse(
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
                debug=self._build_debug(
                    trace_id=trace_id,
                    total_started=total_started,
                    asr_result=asr_result,
                    llm_result=None,
                    tts_result=tts_client_result,
                    speech_service_url=getattr(self.asr, "base_url", None),
                    tts_service_url=getattr(self.tts, "base_url", None),
                    llm_api_base=getattr(self.llm, "api_base", None),
                    rag_route_source=rag_route.source,
                    rag_context_used=False,
                    llm_skipped="mode_switch",
                ),
            )
            self._log_response_ready(
                response,
                trace_id=trace_id,
                asr_source=asr_result.source,
                llm_source="skipped:mode_switch",
                tts_source=tts_client_result.source,
            )
            return response

        policy = get_mode_service(current_mode).get_policy()
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
        response = RobotChatResponse(
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
            debug=self._build_debug(
                trace_id=trace_id,
                total_started=total_started,
                asr_result=asr_result,
                llm_result=llm_result,
                tts_result=tts_client_result,
                speech_service_url=getattr(self.asr, "base_url", None),
                tts_service_url=getattr(self.tts, "base_url", None),
                llm_api_base=getattr(self.llm, "api_base", None),
                rag_route_source=rag_route.source,
                rag_context_used=bool(rag_context),
            ),
        )
        self._log_response_ready(
            response,
            trace_id=trace_id,
            asr_source=asr_result.source,
            llm_source=llm_result.source,
            tts_source=tts_client_result.source,
        )
        return response

    def _emotion_stub(self, asr_text: str) -> EmotionResult:
        if any(token in asr_text for token in ("累", "困", "疲惫")):
            return EmotionResult(label="tired", confidence=0.65, valence="negative", arousal="low")
        if any(token in asr_text for token in ("开心", "高兴", "太好了")):
            return EmotionResult(label="happy", confidence=0.65, valence="positive", arousal="medium")
        return EmotionResult(label="neutral", confidence=0.5)

    def _build_debug(
        self,
        *,
        trace_id: str,
        total_started: float,
        asr_result,
        llm_result,
        tts_result,
        speech_service_url: str | None,
        tts_service_url: str | None,
        llm_api_base: str | None,
        rag_route_source: str,
        rag_context_used: bool,
        llm_skipped: str | None = None,
    ) -> dict:
        llm_source = llm_skipped or (llm_result.source if llm_result else None)
        llm_latency = None if llm_result is None else llm_result.latency_ms
        llm_fallback = False if llm_result is None else llm_result.fallback
        return {
            "trace_id": trace_id,
            "source": "robot_chat_service",
            "asr_source": asr_result.source,
            "llm_source": llm_source,
            "tts_source": tts_result.source,
            "sources": {
                "asr": asr_result.source,
                "llm": llm_source,
                "tts": tts_result.source,
                "rag_route": rag_route_source,
            },
            "latency_ms": {
                "asr": asr_result.latency_ms,
                "llm": llm_latency,
                "tts": tts_result.latency_ms,
                "total": round((perf_counter() - total_started) * 1000, 2),
            },
            "service_urls": {
                "speech_service": speech_service_url,
                "tts_service": tts_service_url,
                "llm_api_base": llm_api_base,
            },
            "fallback": {
                "asr": asr_result.fallback,
                "llm": llm_fallback,
                "tts": tts_result.fallback,
            },
            "rag_context_used": rag_context_used,
            "llm_reasoning_hint": None if llm_result is None else llm_result.reasoning_hint,
            "tts_detail": tts_result.detail,
        }

    def _log_response_ready(
        self,
        response: RobotChatResponse,
        *,
        trace_id: str,
        asr_source: str,
        llm_source: str,
        tts_source: str,
    ) -> None:
        log_event(
            "robot_chat_response_ready",
            trace_id=trace_id,
            session_id=response.session_id,
            turn_id=response.turn_id,
            mode=response.mode.mode_id,
            mode_changed=response.mode_changed,
            active_rag_namespace=response.active_rag_namespace,
            asr_text=response.asr_text,
            reply_text=response.reply_text,
            tts_audio_url=response.tts.audio_url,
            robot_action_expression=response.robot_action.expression,
            robot_action_motion=response.robot_action.motion,
            robot_action_speech_style=response.robot_action.speech_style,
            sources={"asr": asr_source, "llm": llm_source, "tts": tts_source},
        )


robot_chat_service = RobotChatService()

__all__ = ["RobotChatService", "robot_chat_service"]
