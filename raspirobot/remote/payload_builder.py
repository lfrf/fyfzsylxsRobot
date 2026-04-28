from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from shared.schemas import RobotChatRequest, RobotInput, RobotState, VisionContext

from raspirobot.audio.wav_utils import read_wav_info
from raspirobot.utils import encode_file_to_base64, unix_timestamp
from raspirobot.vision import VisionContextProvider
from shared.logging_utils import log_event


@dataclass
class RobotPayloadBuilder:
    session_id: str
    mode_id: str = "elderly"
    vision_context_provider: VisionContextProvider | None = None
    request_options: dict = field(default_factory=dict)

    def build(
        self,
        *,
        wav_path: str | Path,
        turn_id: str,
        state: str = "UPLOADING",
        mode_id: str | None = None,
        robot_state: RobotState | None = None,
    ) -> RobotChatRequest:
        wav_info = read_wav_info(wav_path)
        active_mode = mode_id or self.mode_id
        vision_context: VisionContext | None = None
        if self.vision_context_provider is not None:
            vision_context = self.vision_context_provider.get_context()
        audio_base64 = encode_file_to_base64(wav_info.path)
        log_event(
            "payload_built",
            session_id=self.session_id,
            turn_id=turn_id,
            mode=active_mode,
            sample_rate=wav_info.sample_rate,
            channels=wav_info.channels,
            audio_format="wav",
            audio_base64_len=len(audio_base64),
            duration_ms=wav_info.duration_ms,
            vision_context_present=vision_context is not None,
        )

        return RobotChatRequest(
            session_id=self.session_id,
            turn_id=turn_id,
            timestamp=unix_timestamp(),
            mode=active_mode,
            input=RobotInput(
                type="audio_base64",
                audio_base64=audio_base64,
                audio_format="wav",
                sample_rate=wav_info.sample_rate,
                channels=wav_info.channels,
                duration_ms=wav_info.duration_ms,
            ),
            vision_context=vision_context,
            robot_state=robot_state
            or RobotState(
                state=state,
                current_expression="listening",
                hardware_ready={
                    "microphone": True,
                    "speaker": True,
                    "camera": False,
                    "oled": False,
                    "servo": False,
                },
                mode_id=active_mode,
            ),
            request_options=dict(self.request_options),
        )
