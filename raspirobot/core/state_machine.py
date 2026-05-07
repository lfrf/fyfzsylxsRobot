from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from shared.logging_utils import log_event


class RobotRuntimeState(str, Enum):
    IDLE = "IDLE"
    STANDBY = "STANDBY"          # 待机：唤醒词监听中，OLED 显示 sleep
    WAKE_DETECTED = "WAKE_DETECTED"
    LISTENING = "LISTENING"
    RECORDING = "RECORDING"
    UPLOADING = "UPLOADING"
    THINKING = "THINKING"
    SPEAKING = "SPEAKING"
    BUSY_HINT = "BUSY_HINT"
    ERROR_FALLBACK = "ERROR_FALLBACK"


class RobotEvent(str, Enum):
    WAKE_WORD_DETECTED = "WakeWordDetected"
    WAKE_ACK_DONE = "WakeAckDone"
    SPEECH_START = "SpeechStart"
    SPEECH_END = "SpeechEnd"
    REMOTE_REQUEST_SENT = "RemoteRequestSent"
    REMOTE_RESULT_READY = "RemoteResultReady"
    PLAYBACK_STARTED = "PlaybackStarted"
    PLAYBACK_DONE = "PlaybackDone"
    NEW_SPEECH_INPUT = "NewSpeechInput"
    UTTERANCE_REJECTED = "UtteranceRejected"
    SYSTEM_ERROR = "SystemError"
    RECOVERY_DONE = "RecoveryDone"
    STANDBY_TIMEOUT = "StandbyTimeout"   # 唤醒后超时无语音，回到待机


BUSY_STATES = {
    RobotRuntimeState.UPLOADING,
    RobotRuntimeState.THINKING,
    RobotRuntimeState.SPEAKING,
}


@dataclass
class RobotStateMachine:
    state: RobotRuntimeState = RobotRuntimeState.IDLE
    mode_id: str = "care"
    active_turn_id: str | None = None
    remote_request_in_progress: bool = False
    busy_hint_requested: bool = False
    last_error: str | None = None

    def transition(self, event: RobotEvent, *, turn_id: str | None = None, error: str | None = None) -> RobotRuntimeState:
        from_state = self.state
        self.busy_hint_requested = False

        if event == RobotEvent.SYSTEM_ERROR:
            self.last_error = error or "SYSTEM_ERROR"
            self.remote_request_in_progress = False
            self.state = RobotRuntimeState.ERROR_FALLBACK
            self._log_transition(event, from_state, turn_id=turn_id, error=self.last_error)
            return self.state

        if event == RobotEvent.UTTERANCE_REJECTED:
            self.active_turn_id = None
            self.remote_request_in_progress = False
            self.state = RobotRuntimeState.LISTENING
            self._log_transition(event, from_state, turn_id=turn_id)
            return self.state

        if event == RobotEvent.STANDBY_TIMEOUT:
            self.active_turn_id = None
            self.remote_request_in_progress = False
            self.state = RobotRuntimeState.STANDBY
            self._log_transition(event, from_state, turn_id=turn_id)
            return self.state

        if event == RobotEvent.NEW_SPEECH_INPUT and self.state in BUSY_STATES:
            self.busy_hint_requested = True
            self._log_transition(event, from_state, turn_id=turn_id, busy_hint_requested=True)
            return self.state

        if self.state == RobotRuntimeState.IDLE and event == RobotEvent.WAKE_WORD_DETECTED:
            self.state = RobotRuntimeState.WAKE_DETECTED
        elif self.state == RobotRuntimeState.STANDBY and event == RobotEvent.WAKE_WORD_DETECTED:
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

        self._log_transition(event, from_state, turn_id=turn_id, error=error)
        return self.state

    def apply_mode(self, mode_id: str | None) -> None:
        if mode_id:
            old_mode = self.mode_id
            self.mode_id = mode_id
            log_event(
                "state_machine_mode_applied",
                old_mode=old_mode,
                new_mode=self.mode_id,
            )

    def can_accept_speech(self) -> bool:
        return self.state == RobotRuntimeState.LISTENING

    def _log_transition(
        self,
        event: RobotEvent,
        from_state: RobotRuntimeState,
        *,
        turn_id: str | None = None,
        error: str | None = None,
        busy_hint_requested: bool | None = None,
    ) -> None:
        log_event(
            "state_transition",
            transition_event=event.value,
            from_state=from_state.value,
            to_state=self.state.value,
            turn_id=turn_id,
            mode_id=self.mode_id,
            active_turn_id=self.active_turn_id,
            remote_request_in_progress=self.remote_request_in_progress,
            busy_hint_requested=self.busy_hint_requested if busy_hint_requested is None else busy_hint_requested,
            error=error,
        )
