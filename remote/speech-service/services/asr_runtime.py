import json
from pathlib import Path
from tempfile import NamedTemporaryFile

from config import settings
from models import AudioMeta, SpeechFeatures, TranscribeRequest, TranscribeResponse
from services.audio_stream_buffer import BufferedAudioChunk, audio_stream_buffer
from services.feature_extractor import audio_feature_extractor
from services.speech_emotion_runtime import speech_emotion_runtime
from services.storage import speech_storage
from services.wav_utils import DecodedAudio, decode_audio_base64, decode_wav_audio, encode_wav_audio


class SpeechRuntime:
    def __init__(self) -> None:
        self._pipeline = None
        self._backend = None

    def _ensure_pipeline(self):
        if self._pipeline is not None:
            return self._pipeline

        if self._is_qwen_provider():
            self._pipeline = self._ensure_qwen_pipeline()
            self._backend = "qwen3_asr"
            return self._pipeline

        self._pipeline = self._ensure_belle_pipeline()
        self._backend = "belle_whisper"
        return self._pipeline

    def _ensure_belle_pipeline(self):
        try:
            import torch
            from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("Speech service requires torch and transformers.") from exc

        model_ref = settings.asr_model
        model_path = Path(model_ref)
        local_files_only = model_path.exists()
        torch_dtype = torch.float16 if settings.asr_device.startswith("cuda") else torch.float32

        model = AutoModelForSpeechSeq2Seq.from_pretrained(
            model_ref,
            torch_dtype=torch_dtype,
            low_cpu_mem_usage=True,
            use_safetensors=True,
            local_files_only=local_files_only,
        )
        model.to(settings.asr_device)

        processor = AutoProcessor.from_pretrained(
            model_ref,
            local_files_only=local_files_only,
        )
        self._pipeline = pipeline(
            "automatic-speech-recognition",
            model=model,
            tokenizer=processor.tokenizer,
            feature_extractor=processor.feature_extractor,
            torch_dtype=torch_dtype,
            device=settings.asr_device,
        )
        self._pipeline.model.config.forced_decoder_ids = (
            self._pipeline.tokenizer.get_decoder_prompt_ids(
                language=settings.asr_language,
                task="transcribe",
            )
        )
        return self._pipeline

    def _ensure_qwen_pipeline(self):
        try:
            from qwen_asr import Qwen3ASRModel
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "ASR_PROVIDER is qwen3_asr but qwen-asr package is not installed. "
                "Install with: uv pip install qwen-asr"
            ) from exc

        model_ref = settings.asr_model
        load_kwargs = {
            "device_map": "cuda" if settings.asr_device.startswith("cuda") else "cpu",
            "use_flash_attn": bool(settings.qwen_asr_use_flash_attn and settings.asr_device.startswith("cuda")),
        }
        return Qwen3ASRModel.from_pretrained(model_ref, **load_kwargs)

    def _is_qwen_provider(self) -> bool:
        return settings.asr_provider in {"qwen3_asr", "qwen_asr", "qwen3"}

    def warmup(self) -> None:
        if settings.asr_warmup_enabled:
            if self._is_qwen_provider():
                # Qwen3-ASR warmup is intentionally skipped by default to reduce cold-start memory spikes.
                self._ensure_pipeline()
            else:
                try:
                    import numpy as np
                except ImportError as exc:  # pragma: no cover
                    raise RuntimeError("Speech service requires numpy.") from exc

                pipeline_instance = self._ensure_pipeline()
                pipeline_instance(
                    {
                        "raw": np.zeros(48000, dtype=np.float32),
                        "sampling_rate": 48000,
                    },
                    generate_kwargs={"language": settings.asr_language, "task": "transcribe"},
                )

        speech_emotion_runtime.warmup()

    def transcribe(self, request: TranscribeRequest) -> TranscribeResponse:
        stream_event = (request.audio_stream_event or "").strip().lower()
        stream_key = self._resolve_stream_key(request)

        if stream_event == "clear":
            audio_stream_buffer.clear(key=stream_key)
            return self._build_stream_ack_response(
                request,
                text_source="stream_cleared",
                transcript_confidence=0.0,
            )

        request_chunks = self._decode_request_chunks(request)
        if request_chunks and stream_event in {"append", "commit"}:
            buffered_count = audio_stream_buffer.append(key=stream_key, chunks=request_chunks)
        else:
            buffered_count = 0

        if stream_event == "append":
            return self._build_stream_ack_response(
                request,
                text_source="stream_buffered",
                transcript_confidence=0.2,
                buffered_count=buffered_count,
            )

        if request.user_text.strip() and not request.audio_base64 and not request_chunks and stream_event != "commit":
            return TranscribeResponse(
                transcript_text=request.user_text.strip(),
                text_source="upstream_text",
                transcript_confidence=1.0,
                audio_meta=request.audio_meta,
                speech_features=request.audio_meta and SpeechFeatures(source="upstream_text_only") or None,
                model_ref=settings.asr_model,
                device=settings.asr_device,
            )

        audio_payload = self._resolve_audio_payload(
            request=request,
            stream_event=stream_event,
            stream_key=stream_key,
            request_chunks=request_chunks,
        )
        if audio_payload is None:
            transcript_text = (request.client_asr_text or request.user_text or "").strip()
            return TranscribeResponse(
                transcript_text=transcript_text or "",
                text_source=request.client_asr_source or "speech_service_placeholder",
                transcript_confidence=0.5 if transcript_text else 0.1,
                audio_meta=request.audio_meta,
                speech_features=SpeechFeatures(source="hint_only_speech_features"),
                model_ref=settings.asr_model,
                device=settings.asr_device,
            )

        audio_bytes, base_audio_meta, decoded_audio = audio_payload

        audio_path = speech_storage.persist_audio(
            session_id=request.session_id,
            turn_id=request.turn_id,
            audio_bytes=audio_bytes,
            audio_format=(base_audio_meta.format or "wav").lower(),
        )

        transcript_text = self._run_asr(
            audio_bytes=audio_bytes,
            audio_meta=base_audio_meta,
            decoded_audio=decoded_audio,
        )

        if decoded_audio is not None:
            audio_meta, speech_features = audio_feature_extractor.extract(
                decoded_audio,
                audio_format=(base_audio_meta.format or "wav").lower(),
                transcript=transcript_text,
                transcript_confidence=None,
            )
            audio_meta.source = "remote_speech_service"
            speech_features.source = "remote_speech_service"
        else:
            audio_meta = base_audio_meta
            speech_features = SpeechFeatures(
                transcript_confidence=None,
                emotion_tags=["steady"],
                source="remote_speech_service_metadata_only",
            )

        emotion_result = speech_emotion_runtime.infer(audio_path=audio_path)
        if emotion_result and speech_features:
            speech_features.emotion_tags = _merge_unique_tags(
                emotion_result.emotion_tags,
                speech_features.emotion_tags,
            )
            if speech_features.source:
                speech_features.source = f"{speech_features.source}+{emotion_result.source}"
            else:
                speech_features.source = emotion_result.source

        response = TranscribeResponse(
            transcript_text=transcript_text,
            text_source=f"remote_{settings.asr_provider}",
            transcript_confidence=None,
            audio_meta=audio_meta,
            speech_features=speech_features,
            model_ref=settings.asr_model,
            device=settings.asr_device,
        )
        serialized_response = response.model_dump() if hasattr(response, "model_dump") else response.dict()
        speech_storage.persist_transcription(
            session_id=request.session_id,
            turn_id=request.turn_id,
            payload=json.loads(json.dumps(serialized_response, ensure_ascii=False, default=str)),
        )
        return response

    def _resolve_audio_payload(
        self,
        *,
        request: TranscribeRequest,
        stream_event: str,
        stream_key: str,
        request_chunks: list[BufferedAudioChunk],
    ) -> tuple[bytes, AudioMeta, DecodedAudio | None] | None:
        if stream_event == "commit":
            buffered_chunks = audio_stream_buffer.pop(key=stream_key)
            if buffered_chunks:
                return self._merge_stream_chunks(request, buffered_chunks)
            if request.audio_base64:
                return self._build_single_audio_payload(request)
            return None

        if request.audio_base64:
            return self._build_single_audio_payload(request)

        if request_chunks:
            return self._merge_stream_chunks(request, request_chunks)

        return None

    def _build_single_audio_payload(
        self,
        request: TranscribeRequest,
    ) -> tuple[bytes, AudioMeta, DecodedAudio | None]:
        audio_bytes = decode_audio_base64(request.audio_base64 or "")
        normalized_format = (request.audio_format or "wav").strip().lower() or "wav"
        base_audio_meta = request.audio_meta or AudioMeta(
            format=normalized_format,
            duration_ms=request.audio_duration_ms,
            sample_rate_hz=request.audio_sample_rate_hz,
            channels=request.audio_channels,
            source="remote_speech_service",
        )
        decoded_audio = None
        if normalized_format == "wav":
            try:
                decoded_audio = decode_wav_audio(audio_bytes)
            except ValueError:
                decoded_audio = None
        return audio_bytes, base_audio_meta, decoded_audio

    def _decode_request_chunks(self, request: TranscribeRequest) -> list[BufferedAudioChunk]:
        chunks: list[BufferedAudioChunk] = []
        base_sequence = request.audio_stream_sequence_id or 0
        for index, chunk in enumerate(request.audio_chunks):
            if not chunk.audio_base64:
                continue
            chunk_bytes = decode_audio_base64(chunk.audio_base64)
            sequence_id = chunk.sequence_id if chunk.sequence_id is not None else base_sequence + index
            audio_format = (chunk.audio_format or request.audio_format or "wav").strip().lower() or "wav"
            chunks.append(
                BufferedAudioChunk(
                    sequence_id=sequence_id,
                    audio_bytes=chunk_bytes,
                    audio_format=audio_format,
                    audio_duration_ms=chunk.audio_duration_ms,
                    audio_sample_rate_hz=chunk.audio_sample_rate_hz,
                    audio_channels=chunk.audio_channels,
                )
            )
        return chunks

    def _merge_stream_chunks(
        self,
        request: TranscribeRequest,
        chunks: list[BufferedAudioChunk],
    ) -> tuple[bytes, AudioMeta, DecodedAudio | None]:
        if not chunks:
            raise ValueError("Audio stream is empty.")

        normalized_formats = {(chunk.audio_format or "wav").lower() for chunk in chunks}
        if normalized_formats == {"wav"}:
            decoded_segments: list[DecodedAudio] = []
            for chunk in chunks:
                decoded_segments.append(decode_wav_audio(chunk.audio_bytes))
            merged_decoded = self._concat_decoded_audios(decoded_segments)
            merged_audio_bytes = encode_wav_audio(merged_decoded)
            merged_duration_ms = self._estimate_duration_ms(merged_decoded)
            base_audio_meta = request.audio_meta or AudioMeta(
                format="wav",
                duration_ms=merged_duration_ms,
                sample_rate_hz=merged_decoded.sample_rate_hz,
                channels=merged_decoded.channels,
                source="remote_speech_service_stream_commit",
                frame_count=merged_decoded.frame_count,
            )
            if base_audio_meta.duration_ms is None:
                base_audio_meta.duration_ms = merged_duration_ms
            if base_audio_meta.sample_rate_hz is None:
                base_audio_meta.sample_rate_hz = merged_decoded.sample_rate_hz
            if base_audio_meta.channels is None:
                base_audio_meta.channels = merged_decoded.channels
            return merged_audio_bytes, base_audio_meta, merged_decoded

        fallback_chunk = chunks[-1]
        fallback_audio_meta = request.audio_meta or AudioMeta(
            format=fallback_chunk.audio_format,
            duration_ms=fallback_chunk.audio_duration_ms,
            sample_rate_hz=fallback_chunk.audio_sample_rate_hz,
            channels=fallback_chunk.audio_channels,
            source="remote_speech_service_stream_commit_fallback",
        )
        return fallback_chunk.audio_bytes, fallback_audio_meta, None

    def _build_stream_ack_response(
        self,
        request: TranscribeRequest,
        *,
        text_source: str,
        transcript_confidence: float,
        buffered_count: int | None = None,
    ) -> TranscribeResponse:
        transcript_text = (request.client_asr_text or request.user_text or "").strip()
        speech_features = SpeechFeatures(
            transcript_confidence=transcript_confidence,
            source="speech_stream_buffer",
            emotion_tags=[f"buffered_chunks:{buffered_count}"] if buffered_count is not None else [],
        )
        return TranscribeResponse(
            transcript_text=transcript_text,
            text_source=text_source,
            transcript_confidence=transcript_confidence if transcript_text else 0.0,
            audio_meta=request.audio_meta,
            speech_features=speech_features,
            model_ref=settings.asr_model,
            device=settings.asr_device,
        )

    def _resolve_stream_key(self, request: TranscribeRequest) -> str:
        stream_id = (
            request.audio_stream_id
            or (request.turn_time_window.stream_id if request.turn_time_window else None)
            or f"turn-{request.turn_id}"
        )
        return f"{request.session_id}:{stream_id}"

    def _concat_decoded_audios(self, segments: list[DecodedAudio]) -> DecodedAudio:
        if not segments:
            raise ValueError("No decoded audio segments were provided.")
        first = segments[0]
        sample_rate_hz = first.sample_rate_hz
        channels = first.channels
        sample_width_bytes = first.sample_width_bytes
        merged_samples = [[] for _ in range(channels)]

        for segment in segments:
            if segment.sample_rate_hz != sample_rate_hz or segment.channels != channels:
                raise ValueError("WAV chunks must share the same sample rate and channel count.")
            for channel_index in range(channels):
                merged_samples[channel_index].extend(segment.samples_by_channel[channel_index])

        frame_count = len(merged_samples[0]) if merged_samples else 0
        return DecodedAudio(
            sample_rate_hz=sample_rate_hz,
            channels=channels,
            frame_count=frame_count,
            sample_width_bytes=sample_width_bytes,
            samples_by_channel=merged_samples,
        )

    def _estimate_duration_ms(self, decoded_audio: DecodedAudio) -> int:
        if decoded_audio.sample_rate_hz <= 0:
            return 0
        return int((decoded_audio.frame_count / decoded_audio.sample_rate_hz) * 1000)

    def _run_asr(
        self,
        *,
        audio_bytes: bytes,
        audio_meta: AudioMeta,
        decoded_audio: DecodedAudio | None = None,
    ) -> str:
        pipeline_instance = self._ensure_pipeline()
        if self._backend == "qwen3_asr":
            return self._run_qwen_asr(
                pipeline_instance=pipeline_instance,
                audio_bytes=audio_bytes,
                audio_meta=audio_meta,
                decoded_audio=decoded_audio,
            )

        generate_kwargs = {"language": settings.asr_language, "task": "transcribe"}

        if decoded_audio is not None:
            pipeline_input = self._decoded_audio_to_pipeline_input(decoded_audio)
            result = pipeline_instance(pipeline_input, generate_kwargs=generate_kwargs)
        elif (audio_meta.format or "wav").lower() == "wav":
            decoded_from_bytes = decode_wav_audio(audio_bytes)
            pipeline_input = self._decoded_audio_to_pipeline_input(decoded_from_bytes)
            result = pipeline_instance(pipeline_input, generate_kwargs=generate_kwargs)
        else:
            suffix = f".{(audio_meta.format or 'wav').lower()}"
            with NamedTemporaryFile(suffix=suffix) as temp_audio:
                temp_audio.write(audio_bytes)
                temp_audio.flush()
                result = pipeline_instance(temp_audio.name, generate_kwargs=generate_kwargs)

        if isinstance(result, dict):
            text = str(result.get("text", "")).strip()
        else:
            text = str(result).strip()

        return text or "Audio input received from the remote speech service."

    def _run_qwen_asr(
        self,
        *,
        pipeline_instance,
        audio_bytes: bytes,
        audio_meta: AudioMeta,
        decoded_audio: DecodedAudio | None,
    ) -> str:
        wav_bytes = audio_bytes
        if decoded_audio is not None:
            wav_bytes = encode_wav_audio(decoded_audio)
        elif (audio_meta.format or "wav").lower() != "wav":
            # Qwen3-ASR file-path mode is most stable with WAV input in this service.
            suffix = f".{(audio_meta.format or 'wav').lower()}"
            with NamedTemporaryFile(suffix=suffix) as temp_audio:
                temp_audio.write(audio_bytes)
                temp_audio.flush()
                result = pipeline_instance.transcribe(
                    temp_audio.name,
                    language=self._resolve_qwen_language(),
                    use_itn=settings.qwen_asr_use_itn,
                )
            text = self._extract_qwen_text(result)
            return text or "Audio input received from the remote speech service."

        with NamedTemporaryFile(suffix=".wav") as temp_audio:
            temp_audio.write(wav_bytes)
            temp_audio.flush()
            result = pipeline_instance.transcribe(
                temp_audio.name,
                language=self._resolve_qwen_language(),
                use_itn=settings.qwen_asr_use_itn,
            )
        text = self._extract_qwen_text(result)
        return text or "Audio input received from the remote speech service."

    def _resolve_qwen_language(self) -> str:
        raw = (settings.asr_language or "auto").strip().lower()
        if raw in {"", "auto"}:
            return "auto"
        if raw in {"zh", "zh-cn", "zh_cn", "chinese"}:
            return "Chinese"
        if raw in {"en", "english"}:
            return "English"
        return settings.asr_language

    def _extract_qwen_text(self, result) -> str:
        if result is None:
            return ""
        text_attr = getattr(result, "text", None)
        if isinstance(text_attr, str):
            return text_attr.strip()
        if isinstance(result, dict):
            text = result.get("text")
            if isinstance(text, str):
                return text.strip()
        if isinstance(result, list):
            parts = [self._extract_qwen_text(item) for item in result]
            return " ".join(part for part in parts if part).strip()
        if isinstance(result, str):
            return result.strip()
        return str(result).strip()

    def _decoded_audio_to_pipeline_input(self, decoded_audio: DecodedAudio) -> dict:
        try:
            import numpy as np
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("Speech service requires numpy.") from exc

        if decoded_audio.channels == 1:
            waveform = decoded_audio.samples_by_channel[0]
        else:
            waveform = [
                sum(channel_samples) / decoded_audio.channels
                for channel_samples in zip(*decoded_audio.samples_by_channel, strict=False)
            ]
        return {
            "raw": np.asarray(waveform, dtype=np.float32),
            "sampling_rate": decoded_audio.sample_rate_hz,
        }


def _merge_unique_tags(primary: list[str], secondary: list[str]) -> list[str]:
    merged: list[str] = []
    for item in (primary or []) + (secondary or []):
        text = (item or "").strip()
        if text and text not in merged:
            merged.append(text)
    return merged


speech_runtime = SpeechRuntime()
