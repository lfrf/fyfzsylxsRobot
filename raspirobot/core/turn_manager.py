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
    ) -> None:
        self.payload_builder = payload_builder
        self.remote_client = remote_client
        self.action_dispatcher = action_dispatcher
        self.audio_output = audio_output
        self.session = session
        self.logger = logger or TurnLogger()
        self.audio_preprocessor = audio_preprocessor

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

        if self.audio_preprocessor is not None:
            try:
                preprocess_result = self.audio_preprocessor.process_file(
                    raw_wav_path,
                    output_dir=raw_wav_path.parent,
                )
                payload_wav_path = preprocess_result.used_for_payload_path
            except Exception:
                payload_wav_path = raw_wav_path

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
