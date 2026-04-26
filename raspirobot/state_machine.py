from dataclasses import dataclass
from enum import StrEnum


class RobotRuntimeState(StrEnum):
    IDLE = "IDLE"
    WAKE_DETECTED = "WAKE_DETECTED"
    LISTENING = "LISTENING"
    RECORDING = "RECORDING"
    UPLOADING = "UPLOADING"
    THINKING = "THINKING"
    SPEAKING = "SPEAKING"
    BUSY_HINT = "BUSY_HINT"
    ERROR_FALLBACK = "ERROR_FALLBACK"


class RobotEvent(StrEnum):
    WAKE_WORD_DETECTED = "WakeWordDetected"
    WAKE_ACK_DONE = "WakeAckDone"
    SPEECH_START = "SpeechStart"
    SPEECH_END = "SpeechEnd"
    REMOTE_REQUEST_SENT = "RemoteRequestSent"
    REMOTE_RESULT_READY = "RemoteResultReady"
    PLAYBACK_DONE = "PlaybackDone"
    NEW_SPEECH_INPUT = "NewSpeechInput"
    SYSTEM_ERROR = "SystemError"
    RECOVERY_DONE = "RecoveryDone"


BUSY_STATES = {
    RobotRuntimeState.UPLOADING,
    RobotRuntimeState.THINKING,
    RobotRuntimeState.SPEAKING,
}


@dataclass
class RobotStateMachine:
    state: RobotRuntimeState = RobotRuntimeState.IDLE
    mode_id: str = "elderly"
    active_turn_id: str | None = None
    remote_request_in_progress: bool = False
    busy_hint_requested: bool = False
    last_error: str | None = None

    def transition(self, event: RobotEvent, *, turn_id: str | None = None, error: str | None = None) -> RobotRuntimeState:
        self.busy_hint_requested = False

        if event == RobotEvent.SYSTEM_ERROR:
            self.last_error = error or "SYSTEM_ERROR"
            self.remote_request_in_progress = False
            self.state = RobotRuntimeState.ERROR_FALLBACK
            return self.state

        if event == RobotEvent.NEW_SPEECH_INPUT and self.state in BUSY_STATES:
            self.busy_hint_requested = True
            return self.state

        if self.state == RobotRuntimeState.IDLE and event == RobotEvent.WAKE_WORD_DETECTED:
            self.state = RobotRuntimeState.WAKE_DETECTED
        elif self.state == RobotRuntimeState.WAKE_DETECTED and event == RobotEvent.WAKE_ACK_DONE:
            self.state = RobotRuntimeState.LISTENING
        elif self.state == RobotRuntimeState.LISTENING and event == RobotEvent.SPEECH_START:
            self.state = RobotRuntimeState.RECORDING
        elif self.state == RobotRuntimeState.RECORDING and event == RobotEvent.SPEECH_END:
            self.active_turn_id = turn_id
            self.state = RobotRuntimeState.UPLOADING
        elif self.state == RobotRuntimeState.UPLOADING and event == RobotEvent.REMOTE_REQUEST_SENT:
            self.remote_request_in_progress = True
            self.state = RobotRuntimeState.THINKING
        elif self.state == RobotRuntimeState.THINKING and event == RobotEvent.REMOTE_RESULT_READY:
            self.remote_request_in_progress = False
            self.state = RobotRuntimeState.SPEAKING
        elif self.state == RobotRuntimeState.SPEAKING and event == RobotEvent.PLAYBACK_DONE:
            self.active_turn_id = None
            self.state = RobotRuntimeState.LISTENING
        elif self.state == RobotRuntimeState.ERROR_FALLBACK and event == RobotEvent.RECOVERY_DONE:
            self.active_turn_id = None
            self.last_error = None
            self.state = RobotRuntimeState.LISTENING

        return self.state

    def apply_mode(self, mode_id: str | None) -> None:
        if mode_id:
            self.mode_id = mode_id

