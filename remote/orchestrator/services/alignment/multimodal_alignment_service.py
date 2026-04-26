from models import ChatRequest
from services.alignment.contracts import AlignedTurn


class MultimodalAlignmentService:
    def align(self, request: ChatRequest, transcript: str) -> AlignedTurn:
        alignment_mode = self._resolve_alignment_mode(request)
        speech_context = self._build_speech_context(request)
        vision_context = self._build_vision_context(request)
        alignment_summary = self._build_alignment_summary(
            alignment_mode=alignment_mode,
            speech_context=speech_context,
            vision_context=vision_context,
        )

        llm_user_text = self._build_llm_user_text(
            transcript=transcript,
            alignment_mode=alignment_mode,
            speech_context=speech_context,
            vision_context=vision_context,
        )

        return AlignedTurn(
            canonical_user_text=transcript,
            llm_user_text=llm_user_text,
            alignment_mode=alignment_mode,
            alignment_summary=alignment_summary,
            speech_context=speech_context,
            vision_context=vision_context,
        )

    def _resolve_alignment_mode(self, request: ChatRequest) -> str:
        if request.alignment_mode:
            return request.alignment_mode

        has_vision = bool(request.vision_features)
        if has_vision and request.input_type == "audio":
            return "video_audio"
        if has_vision:
            return "video_text"
        if request.input_type == "audio":
            return "audio_only"
        return "text_only"

    def _build_speech_context(self, request: ChatRequest) -> str | None:
        if not request.speech_features and not request.audio_meta:
            return None

        speech_details: list[str] = []

        if request.speech_features:
            features = request.speech_features
            if features.emotion_tags:
                speech_details.append(f"emotion tags: {', '.join(features.emotion_tags)}")
            if features.speaking_rate is not None:
                speech_details.append(f"speaking rate: {features.speaking_rate}")
            if features.pause_ratio is not None:
                speech_details.append(f"pause ratio: {features.pause_ratio}")
            if features.rms_energy is not None:
                speech_details.append(f"energy: {features.rms_energy}")
            if features.pitch_hz is not None:
                speech_details.append(f"pitch estimate: {features.pitch_hz} Hz")

        if request.audio_meta:
            audio_meta = request.audio_meta
            meta_details = []
            if audio_meta.duration_ms is not None:
                meta_details.append(f"duration: {audio_meta.duration_ms} ms")
            if audio_meta.sample_rate_hz is not None:
                meta_details.append(f"sample rate: {audio_meta.sample_rate_hz} Hz")
            if audio_meta.channels is not None:
                meta_details.append(f"channels: {audio_meta.channels}")
            if meta_details:
                speech_details.append(f"audio meta: {', '.join(meta_details)}")

        if not speech_details:
            return None

        return "; ".join(speech_details)

    def _build_vision_context(self, request: ChatRequest) -> str | None:
        if not request.vision_features:
            return None

        vision_details: list[str] = []
        if request.vision_features.scene_summary:
            vision_details.append(f"scene summary: {request.vision_features.scene_summary}")
        if request.vision_features.attention_target:
            vision_details.append(f"attention target: {request.vision_features.attention_target}")
        if request.vision_features.motion_level:
            vision_details.append(f"motion level: {request.vision_features.motion_level}")
        if request.vision_features.emotion_tags:
            vision_details.append(f"emotion tags: {', '.join(request.vision_features.emotion_tags)}")

        if not vision_details:
            return None

        return "; ".join(vision_details)

    def _build_alignment_summary(
        self,
        *,
        alignment_mode: str,
        speech_context: str | None,
        vision_context: str | None,
    ) -> str | None:
        details = [f"alignment={alignment_mode}"]
        if speech_context:
            details.append("speech=ready")
        if vision_context:
            details.append("vision=ready")
        return " | ".join(details)

    def _build_llm_user_text(
        self,
        *,
        transcript: str,
        alignment_mode: str,
        speech_context: str | None,
        vision_context: str | None,
    ) -> str:
        context_sections = [f"Alignment mode: {alignment_mode}", f"User utterance: {transcript}"]

        if speech_context:
            context_sections.append(f"Speech cues: {speech_context}")
        if vision_context:
            context_sections.append(f"Vision cues: {vision_context}")

        if len(context_sections) <= 2:
            return transcript

        return "\n".join(context_sections)


multimodal_alignment_service = MultimodalAlignmentService()
