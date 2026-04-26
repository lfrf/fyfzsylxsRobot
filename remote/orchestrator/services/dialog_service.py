import time
from datetime import datetime, timezone

from adapters.avatar_client import avatar_client
from adapters.emotion_client import EmotionInferenceResult, emotion_client
from adapters.llm_client import LLMRequest, llm_client
from adapters.speech_client import speech_client
from adapters.vision_client import vision_client
from config import settings
from models import ChatRequest, ChatResponse, EmotionInference, MultimodalEvidence, MultimodalResult, MultimodalSignal
from services.alignment import multimodal_alignment_service
from services.alignment.contracts import AlignedTurn
from services.observability import orchestrator_observability
from services.policy_service import policy_service
from services.prompt_builder import prompt_builder
from services.rag import rag_service, safety_router
from services.rag.contracts import RagResult
from services.session_state import session_state
from services.tts_style_mapper import tts_style_mapper


class DialogService:
    async def build_reply(self, request: ChatRequest) -> ChatResponse:
        started_at = time.perf_counter()
        speech_result = await speech_client.analyze_turn(request)
        enriched_request = self._merge_request(
            request,
            user_text=speech_result.transcript_text,
            text_source=speech_result.text_source,
            audio_meta=speech_result.audio_meta,
            speech_features=speech_result.speech_features,
        )
        vision_features = await vision_client.extract_features(enriched_request)
        enriched_request = self._merge_request(
            enriched_request,
            vision_features=vision_features,
        )
        transcript = speech_result.transcript_text
        if not transcript:
            transcript = "The client sent an empty turn."

        aligned_turn = multimodal_alignment_service.align(enriched_request, transcript)
        emotion_inference = await emotion_client.infer_turn(enriched_request, aligned_turn.canonical_user_text)
        multimodal_result = self._build_multimodal_result(enriched_request, aligned_turn, emotion_inference)
        speech_tags = list(enriched_request.speech_features.emotion_tags) if enriched_request.speech_features else []
        vision_tags = list(enriched_request.vision_features.emotion_tags) if enriched_request.vision_features else []
        route = safety_router.route(
            aligned_turn.canonical_user_text,
            speech_tags=speech_tags,
            vision_tags=vision_tags,
            emotion_tags=list(emotion_inference.emotion_tags),
        )
        rag_result = rag_service.retrieve(
            query=self._build_rag_query(aligned_turn),
            route=route,
        )
        orchestrator_observability.log_alignment_ready(
            request.session_id,
            request.turn_id,
            {
                "alignment_mode": aligned_turn.alignment_mode,
                "alignment_summary": aligned_turn.alignment_summary,
                "speech_context_ready": bool(aligned_turn.speech_context),
                "vision_context_ready": bool(aligned_turn.vision_context),
                "emotion_source": emotion_inference.source,
                "rag_route": route.label,
                "rag_risk_level": route.risk_level,
                "rag_hits": len(rag_result.hits),
                "rag_topics": rag_result.topics,
            },
        )
        context_messages = session_state.build_context_messages(request.session_id)
        memory_summary = session_state.get_summary(request.session_id)
        system_prompt = prompt_builder.build_system_prompt(
            settings.system_prompt,
            context_summary=memory_summary,
            rag_context=rag_result.prompt_context,
            route_label=route.label,
        )
        emotion_style = policy_service.select_emotion_style(enriched_request, transcript)
        avatar_action = policy_service.select_avatar_action(enriched_request, transcript)
        llm_result = await llm_client.generate_reply(
            LLMRequest(
                session_id=request.session_id,
                turn_id=request.turn_id,
                system_prompt=system_prompt,
                user_text=aligned_turn.llm_user_text,
                input_mode=enriched_request.input_type,
                context_messages=context_messages,
                context_summary=memory_summary,
            )
        )
        tts_plan = tts_style_mapper.build_plan(
            emotion_style=emotion_style,
            reply_text=llm_result.reply_text,
        )
        video_reply_text = self._select_video_reply_text(llm_result.reply_text)
        video_is_partial = video_reply_text != llm_result.reply_text.strip()
        avatar_generation = await avatar_client.generate(
            request=enriched_request,
            reply_text=video_reply_text or llm_result.reply_text,
            emotion_style=emotion_style,
            avatar_action=avatar_action,
            tts_plan=tts_plan,
        )

        session_state.append_message(
            request.session_id,
            role="user",
            content=aligned_turn.canonical_user_text,
            turn_id=request.turn_id,
            input_mode=request.input_type,
        )
        session_state.append_message(
            request.session_id,
            role="assistant",
            content=llm_result.reply_text,
            turn_id=request.turn_id,
            input_mode="text",
        )

        response = ChatResponse(
            server_status="ok",
            reply_text=llm_result.reply_text,
            emotion_style=emotion_style,
            avatar_action=avatar_action,
            avatar_output=avatar_generation.avatar_output,
            multimodal_result=multimodal_result,
            server_ts=int(datetime.now(timezone.utc).timestamp()),
            input_mode=enriched_request.input_type,
            reply_audio_url=avatar_generation.reply_audio_url,
            reply_video_url=(
                f"/media/video/{request.session_id}/{request.turn_id}"
                if avatar_generation.reply_video_url
                else None
            ),
            reply_video_stream_url=(
                f"/media/video-stream/{request.session_id}/{request.turn_id}/manifest"
                if avatar_generation.reply_video_stream_url
                else None
            ),
            video_text=video_reply_text or None,
            video_is_partial=video_is_partial,
            response_source=llm_result.response_source,
            context_summary=memory_summary or None,
            reasoning_hint=self._build_reasoning_hint(
                llm_result.reasoning_hint,
                rag_result,
                aligned_turn,
                context_messages,
            ),
            turn_time_window=enriched_request.turn_time_window,
            alignment_mode=aligned_turn.alignment_mode,
        )
        if response.reply_video_url:
            response.reply_video_url = f"{response.reply_video_url}?ts={response.server_ts}"
        if response.reply_video_stream_url:
            response.reply_video_stream_url = f"{response.reply_video_stream_url}?ts={response.server_ts}"
        orchestrator_observability.log_chat_response(
            request.session_id,
            request.turn_id,
            latency_ms=int((time.perf_counter() - started_at) * 1000),
            payload={
                "response_source": response.response_source,
                "alignment_mode": response.alignment_mode,
                "avatar_profile_id": request.avatar_profile_id,
                "emotion_style": response.emotion_style,
                "tts_speed": tts_plan.tts_speed,
                "tts_speaker_id": tts_plan.tts_speaker_id,
                "reply_text_preview": response.reply_text[:200],
                "video_text_preview": (response.video_text or "")[:200],
                "video_is_partial": response.video_is_partial,
                "dominant_emotion": (
                    response.multimodal_result.dominant_emotion if response.multimodal_result else None
                ),
                "multimodal_fusion_summary": (
                    response.multimodal_result.fusion_summary if response.multimodal_result else None
                ),
                "rag_route": route.label,
                "rag_hits": len(rag_result.hits),
                "rag_topics": rag_result.topics,
            },
        )
        return response

    def _build_rag_query(self, aligned_turn: AlignedTurn) -> str:
        parts = [aligned_turn.canonical_user_text or ""]
        if aligned_turn.speech_context:
            parts.append(f"speech: {aligned_turn.speech_context}")
        if aligned_turn.vision_context:
            parts.append(f"vision: {aligned_turn.vision_context}")
        return "\n".join(part for part in parts if part.strip())

    def _build_reasoning_hint(
        self,
        llm_hint: str | None,
        rag_result: RagResult,
        aligned_turn: AlignedTurn,
        context_messages,
    ) -> str | None:
        parts = []
        if llm_hint:
            parts.append(llm_hint)
        parts.append(rag_result.build_reasoning_hint())
        if aligned_turn.alignment_summary:
            parts.append(aligned_turn.alignment_summary)
        elif not llm_hint:
            fallback = prompt_builder.build_reasoning_hint(context_messages)
            if fallback:
                parts.append(fallback)
        return "|".join(part for part in parts if part)

    def _select_video_reply_text(self, reply_text: str) -> str:
        # Keep full assistant reply for avatar TTS/video generation.
        return (reply_text or '').strip()

    def _build_multimodal_result(
        self,
        request: ChatRequest,
        aligned_turn: AlignedTurn,
        emotion_inference: EmotionInferenceResult,
    ) -> MultimodalResult:
        speech_tags = list(request.speech_features.emotion_tags) if request.speech_features else []
        vision_tags = list(request.vision_features.emotion_tags) if request.vision_features else []
        dominant_emotion = emotion_inference.dominant_emotion or self._resolve_dominant_emotion(speech_tags, vision_tags)
        emotion_payload = EmotionInference(
            dominant_emotion=emotion_inference.dominant_emotion,
            emotion_tags=list(emotion_inference.emotion_tags),
            confidence=emotion_inference.confidence,
            source=emotion_inference.source,
            model_ref=emotion_inference.model_ref,
        )

        evidence = MultimodalEvidence(
            canonical_user_text=aligned_turn.canonical_user_text or None,
            speech_context=aligned_turn.speech_context,
            vision_context=aligned_turn.vision_context,
            speech_emotion_tags=speech_tags,
            vision_emotion_tags=vision_tags,
            emotion_inference=emotion_payload,
            audio_duration_ms=(request.audio_meta.duration_ms if request.audio_meta else None),
            video_frame_count=self._resolve_video_frame_count(request),
        )

        return MultimodalResult(
            alignment_mode=aligned_turn.alignment_mode,
            modalities=self._build_modalities(request, aligned_turn, speech_tags, vision_tags),
            dominant_emotion=dominant_emotion,
            fusion_summary=self._build_fusion_summary(
                aligned_turn,
                speech_tags,
                vision_tags,
                dominant_emotion,
                emotion_inference.source,
                emotion_inference.confidence,
            ),
            evidence=evidence,
        )

    def _build_modalities(
        self,
        request: ChatRequest,
        aligned_turn: AlignedTurn,
        speech_tags: list[str],
        vision_tags: list[str],
    ) -> list[MultimodalSignal]:
        modalities: list[MultimodalSignal] = []

        canonical_text = (aligned_turn.canonical_user_text or "").strip()
        if canonical_text:
            modalities.append(
                MultimodalSignal(
                    modality="text",
                    source=request.text_source or "resolved_text",
                    summary=canonical_text[:120],
                )
            )

        has_audio = bool(
            request.input_type == "audio"
            or request.audio_base64
            or request.audio_chunks
            or request.audio_meta
            or request.speech_features
        )
        if has_audio:
            modalities.append(
                MultimodalSignal(
                    modality="audio",
                    source=(
                        request.speech_features.source
                        if request.speech_features and request.speech_features.source
                        else request.audio_meta.source
                        if request.audio_meta and request.audio_meta.source
                        else "speech_service"
                    ),
                    summary=aligned_turn.speech_context,
                    tags=speech_tags,
                    confidence=(
                        request.speech_features.transcript_confidence
                        if request.speech_features
                        else None
                    ),
                )
            )

        has_video = bool(request.vision_features or request.video_frames or request.video_meta)
        if has_video:
            modalities.append(
                MultimodalSignal(
                    modality="video",
                    source=(
                        request.vision_features.source
                        if request.vision_features and request.vision_features.source
                        else request.video_meta.source
                        if request.video_meta and request.video_meta.source
                        else "vision_service"
                    ),
                    summary=aligned_turn.vision_context,
                    tags=vision_tags,
                )
            )

        return modalities

    def _resolve_dominant_emotion(self, speech_tags: list[str], vision_tags: list[str]) -> str | None:
        if not speech_tags and not vision_tags:
            return None

        speech_set = set(speech_tags)
        for tag in vision_tags:
            if tag in speech_set:
                return tag

        if vision_tags:
            return vision_tags[0]
        return speech_tags[0]

    def _build_fusion_summary(
        self,
        aligned_turn: AlignedTurn,
        speech_tags: list[str],
        vision_tags: list[str],
        dominant_emotion: str | None,
        emotion_source: str | None,
        emotion_confidence: float | None,
    ) -> str:
        parts = [f"mode={aligned_turn.alignment_mode}"]
        if speech_tags:
            parts.append(f"speech_tags={','.join(speech_tags[:3])}")
        if vision_tags:
            parts.append(f"vision_tags={','.join(vision_tags[:3])}")
        if dominant_emotion:
            parts.append(f"dominant_emotion={dominant_emotion}")
        if emotion_source:
            parts.append(f"emotion_source={emotion_source}")
        if emotion_confidence is not None:
            parts.append(f"emotion_confidence={emotion_confidence:.2f}")
        if aligned_turn.alignment_summary:
            parts.append(aligned_turn.alignment_summary)
        return " | ".join(parts)

    def _resolve_video_frame_count(self, request: ChatRequest) -> int | None:
        if request.vision_features and request.vision_features.frame_count is not None:
            return request.vision_features.frame_count
        if request.video_meta and request.video_meta.sampled_frame_count is not None:
            return request.video_meta.sampled_frame_count
        if request.video_frames:
            return len(request.video_frames)
        return None

    def _merge_request(self, request: ChatRequest, **updates) -> ChatRequest:
        normalized_updates = {key: value for key, value in updates.items()}
        if hasattr(request, "model_copy"):
            return request.model_copy(update=normalized_updates)
        return request.copy(update=normalized_updates)


dialog_service = DialogService()
