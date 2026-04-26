from dataclasses import dataclass

import httpx

from config import Settings
from hardware import AudioPlayer, EyesController, HeadController
from models import ChatForwardPayload


@dataclass
class RobotRuntime:
    settings: Settings
    eyes: EyesController
    head: HeadController
    audio: AudioPlayer
    last_reply_text: str | None = None
    last_emotion_style: str | None = None

    @classmethod
    def from_settings(cls, settings: Settings) -> "RobotRuntime":
        return cls(
            settings=settings,
            eyes=EyesController(mode=settings.eyes_mode),
            head=HeadController(
                mode=settings.servo_mode,
                pan_channel=settings.servo_pan_channel,
                tilt_channel=settings.servo_tilt_channel,
                min_degree=settings.servo_min_degree,
                max_degree=settings.servo_max_degree,
            ),
            audio=AudioPlayer(mode=settings.audio_mode),
        )

    async def forward_text_chat(self, payload: ChatForwardPayload) -> dict:
        url = f"{self.settings.edge_backend_base}/chat"
        async with httpx.AsyncClient(timeout=self.settings.chat_timeout_seconds) as client:
            response = await client.post(url, json=payload.model_dump())
            response.raise_for_status()
            data = response.json()
        self.last_reply_text = data.get("reply_text")
        self.last_emotion_style = data.get("emotion_style")
        self._apply_expression_from_response(data)
        if self.last_reply_text:
            self.audio.play_text(self.last_reply_text)
        return data

    def _apply_expression_from_response(self, response_json: dict) -> None:
        style = (response_json.get("emotion_style") or "").strip().lower()
        action = response_json.get("avatar_action") or {}
        expression = (
            action.get("facial_expression")
            or ("happy" if style in {"happy", "excited"} else "neutral")
        )
        motion = (action.get("head_motion") or "").strip().lower()

        self.eyes.set_expression(expression)
        if motion == "nod":
            self.head.set_pose(90, 95)
        elif motion == "turn_left":
            self.head.set_pose(100, 90)
        elif motion == "turn_right":
            self.head.set_pose(80, 90)
        else:
            self.head.center()
