from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from raspirobot.audio.preprocessor import AudioPreprocessor
from shared.schemas import RobotChatResponse

from raspirobot.actions import RobotActionDispatcher
from raspirobot.audio import AudioOutputProvider, PlaybackResult
from raspirobot.remote import RemoteClientProtocol, RobotPayloadBuilder
from raspirobot.session import SessionManager, TurnLogger
from shared.logging_utils import log_event


class UtteranceRejected(Exception):
    """Raised when an utterance is rejected due to preprocessing fallback or other criteria."""
    
    def __init__(self, reason: str, *, wav_path: Path, preprocess_result: Any = None):
        self.reason = reason
        self.wav_path = wav_path
        self.preprocess_result = preprocess_result
        super().__init__(f"Utterance rejected: {reason}")


@dataclass
class TurnResult:
    response: RobotChatResponse
    playback: PlaybackResult | None = None


class TurnManager:
    def __init__(
        self,
        *,
        payload_builder: RobotPayloadBuilder,
        remote_client: RemoteClientProtocol,
        action_dispatcher: RobotActionDispatcher,
        audio_output: AudioOutputProvider,
        session: SessionManager,
        logger: TurnLogger | None = None,
        audio_preprocessor: AudioPreprocessor | None = None,
        audio_drop_invalid_utterance: bool = False,
        audio_drop_reasons: str = "no_speech_detected,speech_too_short",
    ) -> None:
        self.payload_builder = payload_builder
        self.remote_client = remote_client
        self.action_dispatcher = action_dispatcher
        self.audio_output = audio_output
        self.session = session
        self.logger = logger or TurnLogger()
        self.audio_preprocessor = audio_preprocessor
        self.audio_drop_invalid_utterance = audio_drop_invalid_utterance
        # Parse drop reasons into a set for efficient lookup
        self.audio_drop_reasons_set = set(
            reason.strip() for reason in audio_drop_reasons.split(",") if reason.strip()
        )

    def handle_utterance(
        self,
        wav_path: str | Path,
        *,
        state: str = "UPLOADING",
        before_playback: Callable[[RobotChatResponse], None] | None = None,
    ) -> TurnResult:
        raw_wav_path = Path(wav_path)
        payload_wav_path = raw_wav_path
        preprocess_result = None
        preprocess_enabled = False

        if self.audio_preprocessor is not None:
            preprocess_enabled = True
            try:
                preprocess_result = self.audio_preprocessor.process_file(
                    raw_wav_path,
                    output_dir=raw_wav_path.parent,
                )
                payload_wav_path = preprocess_result.used_for_payload_path
            except Exception:
                payload_wav_path = raw_wav_path

        # Log audio payload selection with detailed metrics
        log_event(
            "audio_payload_selected",
            raw_wav_path=str(raw_wav_path),
            clean_wav_path=str(preprocess_result.clean_wav_path) if preprocess_result and preprocess_result.clean_wav_path else None,
            payload_wav_path=str(payload_wav_path),
            preprocess_enabled=preprocess_enabled,
            preprocess_fallback_used=preprocess_result.fallback_used if preprocess_result else None,
            preprocess_fallback_reason=preprocess_result.fallback_reason if preprocess_result else None,
            raw_duration_ms=preprocess_result.raw_duration_ms if preprocess_result else None,
            clean_duration_ms=preprocess_result.clean_duration_ms if preprocess_result else None,
            trimmed_head_ms=preprocess_result.trimmed_head_ms if preprocess_result else None,
            trimmed_tail_ms=preprocess_result.trimmed_tail_ms if preprocess_result else None,
            noise_floor_rms=preprocess_result.noise_floor_rms if preprocess_result else None,
            noise_floor_strategy=preprocess_result.noise_floor_strategy if preprocess_result else None,
            gate_threshold_rms=preprocess_result.gate_threshold_rms if preprocess_result else None,
            speech_peak_rms=preprocess_result.speech_peak_rms if preprocess_result else None,
            speech_mean_rms=preprocess_result.speech_mean_rms if preprocess_result else None,
            speech_frames=preprocess_result.speech_frames if preprocess_result else None,
            muted_frames=preprocess_result.muted_frames if preprocess_result else None,
            debug_json_path=str(preprocess_result.debug_json_path) if preprocess_result and preprocess_result.debug_json_path else None,
        )

        # Check if utterance should be dropped due to invalid preprocessing result
        if (
            self.audio_drop_invalid_utterance
            and preprocess_result is not None
            and preprocess_result.fallback_reason in self.audio_drop_reasons_set
        ):
            log_event(
                "utterance_dropped_after_preprocess",
                raw_wav_path=str(raw_wav_path),
                fallback_reason=preprocess_result.fallback_reason,
                speech_duration_ms=preprocess_result.speech_duration_ms,
                raw_duration_ms=preprocess_result.raw_duration_ms,
                noise_floor_rms=preprocess_result.noise_floor_rms,
                gate_threshold_rms=preprocess_result.gate_threshold_rms,
                speech_peak_rms=preprocess_result.speech_peak_rms,
                speech_mean_rms=preprocess_result.speech_mean_rms,
                debug_json_path=str(preprocess_result.debug_json_path) if preprocess_result.debug_json_path else None,
            )
            raise UtteranceRejected(
                f"preprocess fallback: {preprocess_result.fallback_reason}",
                wav_path=raw_wav_path,
                preprocess_result=preprocess_result,
            )

        turn_id = self.session.next_turn_id()
        request = self.payload_builder.build(
            wav_path=payload_wav_path,
            turn_id=turn_id,
            state=state,
            mode_id=self.session.mode_id,
        )

        response = self.remote_client.chat_turn(request)
        self.session.apply_mode(response.mode.mode_id if response.mode else None)
        self.payload_builder.mode_id = self.session.mode_id

        if before_playback is not None:
            before_playback(response)

        log_event(
            "remote_response_received",
            session_id=response.session_id,
            turn_id=response.turn_id,
            asr_text=response.asr_text,
            asr_source=response.debug.get("asr_source") if response.debug else None,
            asr_fallback=(
                response.debug.get("fallback", {}).get("asr")
                if response.debug and isinstance(response.debug.get("fallback"), dict)
                else None
            ),
            reply_text=response.reply_text,
            tts_audio_url=response.tts.audio_url if response.tts else None,
            mode=response.mode.mode_id if response.mode else None,
            mode_changed=response.mode_changed,
            active_rag_namespace=response.active_rag_namespace,
            robot_action={
                "expression": response.robot_action.expression,
                "motion": response.robot_action.motion,
                "speech_style": response.robot_action.speech_style,
            },
        )
        self.action_dispatcher.dispatch(response.robot_action)

        playback = self.audio_output.play_audio_url(
            response.tts.audio_url if response.tts else None,
            base_url=getattr(self.remote_client, "base_url", None),
        )

        self.logger.log(
            {
                "session_id": response.session_id,
                "turn_id": response.turn_id,
                "raw_wav_path": str(raw_wav_path),
                "clean_wav_path": str(preprocess_result.clean_wav_path) if preprocess_result and preprocess_result.clean_wav_path else None,
                "payload_wav_path": str(payload_wav_path),
                "preprocess_enabled": preprocess_enabled,
                "preprocess_fallback_used": preprocess_result.fallback_used if preprocess_result else None,
                "preprocess_fallback_reason": preprocess_result.fallback_reason if preprocess_result else None,
                "raw_duration_ms": preprocess_result.raw_duration_ms if preprocess_result else None,
                "clean_duration_ms": preprocess_result.clean_duration_ms if preprocess_result else None,
                "trimmed_head_ms": preprocess_result.trimmed_head_ms if preprocess_result else None,
                "trimmed_tail_ms": preprocess_result.trimmed_tail_ms if preprocess_result else None,
                "noise_floor_rms": preprocess_result.noise_floor_rms if preprocess_result else None,
                "noise_floor_strategy": preprocess_result.noise_floor_strategy if preprocess_result else None,
                "gate_threshold_rms": preprocess_result.gate_threshold_rms if preprocess_result else None,
                "speech_peak_rms": preprocess_result.speech_peak_rms if preprocess_result else None,
                "speech_mean_rms": preprocess_result.speech_mean_rms if preprocess_result else None,
                "speech_frames": preprocess_result.speech_frames if preprocess_result else None,
                "muted_frames": preprocess_result.muted_frames if preprocess_result else None,
                "debug_json_path": str(preprocess_result.debug_json_path) if preprocess_result and preprocess_result.debug_json_path else None,
                "mode": self.session.mode_id,
                "success": response.success,
                "asr_text": response.asr_text,
                "reply_text": response.reply_text,
                "tts_audio_url": response.tts.audio_url if response.tts else None,
                "playback": self._playback_payload(playback),
            }
        )
        return TurnResult(response=response, playback=playback)

    def _playback_payload(self, playback: PlaybackResult | None) -> dict[str, Any] | None:
        if playback is None:
            return None
        return {
            "played": playback.played,
            "source": playback.source,
            "local_path": str(playback.local_path) if playback.local_path else None,
            "skipped_reason": playback.skipped_reason,
        }
