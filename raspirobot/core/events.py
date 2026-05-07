from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RuntimeEventType(str, Enum):
    SPEECH_STARTED = "SpeechStarted"
    SPEECH_ENDED = "SpeechEnded"
    UTTERANCE_READY = "UtteranceReady"
    REMOTE_REQUEST_STARTED = "RemoteRequestStarted"
    REMOTE_RESULT_READY = "RemoteResultReady"
    REMOTE_REQUEST_FAILED = "RemoteRequestFailed"
    PLAYBACK_STARTED = "PlaybackStarted"
    PLAYBACK_DONE = "PlaybackDone"
    ROBOT_ACTION_RECEIVED = "RobotActionReceived"
    SYSTEM_ERROR = "SystemError"


@dataclass(frozen=True)
class RuntimeEvent:
    type: RuntimeEventType
    payload: dict[str, Any] = field(default_factory=dict)
