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
from logging_utils import log_context, log_event
from services.mode_chains.base import ModeTurnContext
from services.mode_chains.router import ModeChainRouter, mode_chain_router
from services.mode_manager import ModeManager, mode_manager
from services.mode_policy import get_mode_service
from services.rag_router import RagRouter, rag_router
from services.response_policy_service import ResponsePolicyService, response_policy_service
from services.robot_action_service import RobotActionService, robot_action_service
from services.games.game_state_service import game_state_service
from services.profile import UserProfileService, user_profile_service


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
        response_policy: ResponsePolicyService | None = None,
        mode_chain_router_instance: ModeChainRouter | None = None,
        profile_service: UserProfileService | None = None,
    ) -> None:
        self.modes = modes or mode_manager
        self.rag = rag or rag_router
        self.asr = asr or asr_client
        self.llm = llm or llm_client
        self.tts = tts or tts_client
        self.rag_client = rag_client_instance or rag_client
        self.actions = actions or robot_action_service
        self.response_policy = response_policy or response_policy_service
        self.mode_chain_router = mode_chain_router_instance or mode_chain_router
        self.profile_service = profile_service or user_profile_service

    def handle_chat_turn(self, request: RobotChatRequest) -> RobotChatResponse:
        log_session_id = self._request_log_session_id(request)
        with log_context(
            log_session_id=log_session_id,
            robot_session_id=request.session_id,
            robot_turn_id=request.turn_id,
            component="remote_orchestrator",
        ):
            return self._handle_chat_turn(request)

    def _handle_chat_turn(self, request: RobotChatRequest) -> RobotChatResponse:
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
        identity = self.profile_service.resolve_identity(request)
        profile_context_result = self.profile_service.build_profile_context(
            user_id=identity.user_id,
            mode_id=current_mode,
        )

        # ===== GAME MODE LOGIC (highest priority for exits) =====
        # Check for game exit intent (highest priority) - return to care mode
        if game_state_service.detect_exit_intent(asr_text):
            if game_state_service.is_active(request.session_id):
                game_state_service.reset(request.session_id)
                # Sync session mode to care after game exit.
                self.modes.set_session_mode(request.session_id, "care")
                reply_text = "好的，那我们先不玩了。已回到关怀模式，我们可以继续聊天。"
                emotion = EmotionResult(label="neutral", confidence=1.0)
                policy = get_mode_service("care").get_policy()
                rag_route = self.rag.route_for_mode(policy)
                robot_action = self.actions.for_chat(policy, emotion)
                tts_client_result = self.tts.synthesize(
                    text=reply_text,
                    session_id=request.session_id,
                    turn_id=request.turn_id,
                    mode=policy.mode_id,
                    speech_style=policy.speech_style,
                )
                memory_result = self._record_profile_turn(
                    identity=identity,
                    request=request,
                    mode_id=policy.mode_id,
                    asr_text=asr_text,
                    reply_text=reply_text,
                    emotion=emotion,
                )
                response = RobotChatResponse(
                    success=True,
                    session_id=request.session_id,
                    turn_id=request.turn_id,
                    mode=policy.to_mode_info(),
                    mode_switch=ModeSwitchResult(
                        switched=True,
                        from_mode=current_mode,
                        to_mode=policy.mode_id,
                        reason="game exit detected",
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
                        rag_route_source="game_exit",
                        rag_context_used=False,
                        rag_matched_files=[],
                        rag_context_chars=0,
                        rag_used_default_docs=False,
                        requested_mode=request.mode,
                        current_mode=policy.mode_id,
                        display_name=policy.display_name,
                        active_rag_namespace=rag_route.namespace,
                        llm_skipped="game_exit",
                        profile_debug=self._profile_debug(
                            identity=identity,
                            profile_context_result=profile_context_result,
                            memory_result=memory_result,
                        ),
                    ),
                )
                self._log_response_ready(
                    response,
                    trace_id=trace_id,
                    asr_source=asr_result.source,
                    llm_source="skipped:game_exit",
                    tts_source=tts_client_result.source,
                    rag_context_used=False,
                    rag_matched_files=[],
                )
                return response

        # Check for explicit mode switch
        switch = self.modes.detect_switch(asr_text)
        if switch.detected and switch.target_mode:
            # If switching away from game, reset game state
            if switch.target_mode != "game" and game_state_service.is_active(request.session_id):
                game_state_service.reset(request.session_id)

            target_mode = self.modes.set_session_mode(request.session_id, switch.target_mode)
            if target_mode == "game":
                game_state_service.start_choosing(request.session_id)
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
            memory_result = self._record_profile_turn(
                identity=identity,
                request=request,
                mode_id=policy.mode_id,
                asr_text=asr_text,
                reply_text=reply_text,
                emotion=emotion,
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
                    rag_matched_files=[],
                    rag_context_chars=0,
                    rag_used_default_docs=False,
                    requested_mode=request.mode,
                    current_mode=target_mode,
                    display_name=policy.display_name,
                    active_rag_namespace=rag_route.namespace,
                    llm_skipped="mode_switch",
                    profile_debug=self._profile_debug(
                        identity=identity,
                        profile_context_result=profile_context_result,
                        memory_result=memory_result,
                    ),
                ),
            )
            self._log_response_ready(
                response,
                trace_id=trace_id,
                asr_source=asr_result.source,
                llm_source="skipped:mode_switch",
                tts_source=tts_client_result.source,
                rag_context_used=False,
                rag_matched_files=[],
            )
            return response

        # Check for game start intent
        if game_state_service.detect_start_intent(asr_text):
            target_mode = self.modes.set_session_mode(request.session_id, "game")
            game_state_service.start_choosing(request.session_id)
            reply_text = "好呀，我们来玩什么游戏呢？A 猜谜语，B 词语接龙。"
            emotion = EmotionResult(label="happy", confidence=0.8)
            policy = get_mode_service("game").get_policy()
            robot_action = self.actions.for_chat(policy, emotion)
            tts_client_result = self.tts.synthesize(
                text=reply_text,
                session_id=request.session_id,
                turn_id=request.turn_id,
                mode="game",
                speech_style=policy.speech_style,
            )
            memory_result = self._record_profile_turn(
                identity=identity,
                request=request,
                mode_id=policy.mode_id,
                asr_text=asr_text,
                reply_text=reply_text,
                emotion=emotion,
            )
            response = RobotChatResponse(
                success=True,
                session_id=request.session_id,
                turn_id=request.turn_id,
                mode=policy.to_mode_info(),
                mode_switch=ModeSwitchResult(
                    switched=False,
                    from_mode=current_mode,
                    to_mode="game",
                ),
                mode_changed=False,
                active_rag_namespace="game",
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
                    rag_route_source="game_start",
                    rag_context_used=False,
                    rag_matched_files=[],
                    rag_context_chars=0,
                    rag_used_default_docs=False,
                    requested_mode=request.mode,
                    current_mode="game",
                    display_name="游戏模式",
                    active_rag_namespace="game",
                    llm_skipped="game_start",
                    profile_debug=self._profile_debug(
                        identity=identity,
                        profile_context_result=profile_context_result,
                        memory_result=memory_result,
                    ),
                ),
            )
            self._log_response_ready(
                response,
                trace_id=trace_id,
                asr_source=asr_result.source,
                llm_source="skipped:game_start",
                tts_source=tts_client_result.source,
                rag_context_used=False,
                rag_matched_files=[],
            )
            return response

        # ===== END GAME MODE LOGIC =====

        policy = get_mode_service(current_mode).get_policy()
        rag_route = self.rag.route_for_mode(policy)
        log_event(
            "mode_resolved",
            trace_id=trace_id,
            session_id=request.session_id,
            turn_id=request.turn_id,
            requested_mode=request.mode,
            current_mode=current_mode,
            display_name=policy.display_name,
            rag_namespace=rag_route.namespace,
            speech_style=policy.speech_style,
        )
        rag_context = self.rag_client.retrieve_context(namespace=rag_route.namespace, query=asr_text)
        rag_matched_files = list(getattr(self.rag_client, "last_matched_files", []))
        rag_context_chars = int(getattr(self.rag_client, "last_context_chars", len(rag_context or "")) or 0)
        rag_used_default_docs = bool(getattr(self.rag_client, "last_used_default_docs", False))
        emotion = self._emotion_stub(asr_text)

        # Try ModeChainRouter for care/accompany/learning/game
        mode_chain = self.mode_chain_router.get_chain(current_mode)
        chain_context = ModeTurnContext(
            session_id=request.session_id,
            turn_id=request.turn_id,
            mode_id=current_mode,
            asr_text=asr_text,
            mode_policy=policy,
            rag_route=rag_route,
            rag_context=rag_context,
            emotion_label=emotion.label,
            vision_context=request.vision_context,
            robot_state=request.robot_state,
            metadata={
                "identity": self._model_dump(identity),
                "profile": self._model_dump(identity.profile),
                "profile_context": profile_context_result.context,
            },
        )
        chain_result = mode_chain.handle_turn(
            context=chain_context,
            llm_client=self.llm,
            response_policy_service=self.response_policy,
        )

        mode_before_chain_update = current_mode
        mode_changed_by_chain = False

        # Use chain result if handled, otherwise fallback to generic LLM flow
        if chain_result.handled:
            reply_text = (
                chain_result.reply_text
                or getattr(policy, "normal_reply", None)
                or "我听到了，我们继续。"
            )
            llm_result = chain_result.llm_result
            response_policy_changed = chain_result.debug.get("response_policy_changed", False)
            response_policy_rules = chain_result.debug.get("response_policy_rules", [])
            response_policy_original_chars = chain_result.debug.get("response_policy_original_chars", 0)
            response_policy_final_chars = chain_result.debug.get("response_policy_final_chars", 0)
            mode_chain_used = True

            # Handle mode update from game chain
            mode_update = chain_result.debug.get("mode_update")
            if mode_update and mode_update != current_mode:
                self.modes.set_session_mode(request.session_id, mode_update)
                current_mode = mode_update
                policy = get_mode_service(current_mode).get_policy()
                rag_route = self.rag.route_for_mode(policy)
                mode_changed_by_chain = True

            # Use robot_action_hint from chain if provided
            if chain_result.robot_action_hint and not mode_changed_by_chain:
                robot_action = self.actions.create_custom_action(
                    expression=chain_result.robot_action_hint.get("expression", "neutral"),
                    motion=chain_result.robot_action_hint.get("motion", "idle"),
                    speech_style=chain_result.robot_action_hint.get("speech_style", policy.speech_style),
                )
            else:
                robot_action = self.actions.for_chat(policy, emotion)
        else:
            # Fallback: use generic LLM + response_policy flow
            llm_result = self.llm.generate_reply(
                session_id=request.session_id,
                turn_id=request.turn_id,
                asr_text=asr_text,
                mode_policy=policy,
                rag_route=rag_route,
                rag_context=rag_context,
                user_profile_context=profile_context_result.context,
            )
            reply_text = llm_result.reply_text
            response_policy_result = self.response_policy.apply(
                mode_id=policy.mode_id,
                reply_text=reply_text,
                user_text=asr_text,
            )
            reply_text = response_policy_result.reply_text
            response_policy_changed = response_policy_result.changed
            response_policy_rules = response_policy_result.rules_applied
            response_policy_original_chars = response_policy_result.original_chars
            response_policy_final_chars = response_policy_result.final_chars
            mode_chain_used = False
            robot_action = self.actions.for_chat(policy, emotion)

        llm_source = self._safe_llm_source(
            llm_result,
            "skipped:game_chain" if mode_chain_used and chain_result.llm_result is None else "mode_chain",
        )
        tts_client_result = self.tts.synthesize(
            text=reply_text,
            session_id=request.session_id,
            turn_id=request.turn_id,
            mode=policy.mode_id,
            speech_style=policy.speech_style,
        )
        memory_result = self._record_profile_turn(
            identity=identity,
            request=request,
            mode_id=policy.mode_id,
            asr_text=asr_text,
            reply_text=reply_text,
            emotion=emotion,
        )
        response = RobotChatResponse(
            success=True,
            session_id=request.session_id,
            turn_id=request.turn_id,
            mode=policy.to_mode_info(),
            mode_switch=ModeSwitchResult(
                switched=mode_changed_by_chain,
                from_mode=mode_before_chain_update,
                to_mode=current_mode,
                reason="mode chain update" if mode_changed_by_chain else None,
                confirmation_text=reply_text if mode_changed_by_chain else None,
            ),
            mode_changed=mode_changed_by_chain,
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
                rag_matched_files=rag_matched_files,
                rag_context_chars=rag_context_chars,
                rag_used_default_docs=rag_used_default_docs,
                requested_mode=request.mode,
                current_mode=current_mode,
                display_name=policy.display_name,
                active_rag_namespace=rag_route.namespace,
                mode_chain_used=mode_chain_used,
                mode_chain_id=mode_chain.mode_id,
                mode_chain_result=chain_result,
                response_policy_changed=response_policy_changed,
                response_policy_rules=response_policy_rules,
                response_policy_original_chars=response_policy_original_chars,
                response_policy_final_chars=response_policy_final_chars,
                llm_skipped=llm_source if llm_result is None else None,
                profile_debug=self._profile_debug(
                    identity=identity,
                    profile_context_result=profile_context_result,
                    memory_result=memory_result,
                ),
            ),
        )
        self._log_response_ready(
            response,
            trace_id=trace_id,
            asr_source=asr_result.source,
            llm_source=llm_source,
            tts_source=tts_client_result.source,
            rag_context_used=bool(rag_context),
            rag_matched_files=rag_matched_files,
        )
        return response

    def _emotion_stub(self, asr_text: str) -> EmotionResult:
        if any(token in asr_text for token in ("累", "困", "疲惫")):
            return EmotionResult(label="tired", confidence=0.65, valence="negative", arousal="low")
        if any(token in asr_text for token in ("开心", "高兴", "太好了")):
            return EmotionResult(label="happy", confidence=0.65, valence="positive", arousal="medium")
        return EmotionResult(label="neutral", confidence=0.5)

    def _record_profile_turn(
        self,
        *,
        identity,
        request: RobotChatRequest,
        mode_id: str,
        asr_text: str,
        reply_text: str,
        emotion: EmotionResult,
    ):
        return self.profile_service.record_turn(
            user_id=identity.user_id,
            session_id=request.session_id,
            turn_id=request.turn_id,
            mode_id=mode_id,
            asr_text=asr_text,
            reply_text=reply_text,
            emotion_label=emotion.label if emotion else None,
            face_id=identity.face_id,
            request_options=request.request_options,
        )

    def _profile_debug(self, *, identity, profile_context_result, memory_result=None) -> dict:
        return {
            "used": bool(identity and identity.user_id),
            "user_id": getattr(identity, "user_id", None),
            "identity_source": getattr(identity, "identity_source", None),
            "face_id": getattr(identity, "face_id", None),
            "profile_context_chars": getattr(profile_context_result, "chars", 0) or 0,
            "memory_written": bool(getattr(memory_result, "written", False)),
            "summary_updated": bool(getattr(memory_result, "summary_updated", False)),
        }

    def _model_dump(self, model) -> dict:
        if model is None:
            return {}
        if hasattr(model, "model_dump"):
            return model.model_dump()
        if hasattr(model, "dict"):
            return model.dict()
        return dict(model)

    def _safe_llm_source(self, llm_result, fallback: str) -> str:
        if llm_result is None:
            return fallback
        return getattr(llm_result, "source", None) or fallback

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
        rag_matched_files: list[str] | None = None,
        rag_context_chars: int = 0,
        rag_used_default_docs: bool = False,
        requested_mode: str | None = None,
        current_mode: str | None = None,
        display_name: str | None = None,
        active_rag_namespace: str | None = None,
        llm_skipped: str | None = None,
        mode_chain_used: bool = False,
        mode_chain_id: str | None = None,
        mode_chain_result=None,
        response_policy_changed: bool = False,
        response_policy_rules: list[str] | None = None,
        response_policy_original_chars: int = 0,
        response_policy_final_chars: int = 0,
        profile_debug: dict | None = None,
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
            "mode": {
                "requested_mode": requested_mode,
                "current_mode": current_mode,
                "display_name": display_name,
                "active_rag_namespace": active_rag_namespace,
            },
            "rag_context_used": rag_context_used,
            "rag_matched_files": rag_matched_files or [],
            "rag_context_chars": rag_context_chars,
            "rag_used_default_docs": rag_used_default_docs,
            "llm_reasoning_hint": None if llm_result is None else llm_result.reasoning_hint,
            "tts_detail": tts_result.detail,
            "mode_chain": {
                "used": mode_chain_used,
                "mode_chain_id": mode_chain_id,
                "handled": mode_chain_result.handled if mode_chain_result else False,
                "debug": mode_chain_result.debug if mode_chain_result else {},
            },
            "response_policy": {
                "changed": response_policy_changed,
                "original_chars": response_policy_original_chars,
                "final_chars": response_policy_final_chars,
                "rules_applied": response_policy_rules or [],
            },
            "profile": profile_debug or {
                "used": False,
                "user_id": None,
                "identity_source": None,
                "face_id": None,
                "profile_context_chars": 0,
                "memory_written": False,
                "summary_updated": False,
            },
        }

    def _log_response_ready(
        self,
        response: RobotChatResponse,
        *,
        trace_id: str,
        asr_source: str,
        llm_source: str,
        tts_source: str,
        rag_context_used: bool,
        rag_matched_files: list[str],
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
            reply_chars=len(response.reply_text or ""),
            tts_audio_url=response.tts.audio_url,
            robot_action_expression=response.robot_action.expression,
            robot_action_motion=response.robot_action.motion,
            robot_action_speech_style=response.robot_action.speech_style,
            rag_context_used=rag_context_used,
            rag_matched_files=rag_matched_files,
            sources={"asr": asr_source, "llm": llm_source, "tts": tts_source},
        )


    def _request_log_session_id(self, request: RobotChatRequest) -> str:
        options = request.request_options if isinstance(request.request_options, dict) else {}
        return str(options.get("log_session_id") or request.session_id)


robot_chat_service = RobotChatService()

__all__ = ["RobotChatService", "robot_chat_service"]
