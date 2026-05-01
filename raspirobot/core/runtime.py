from __future__ import annotations

from dataclasses import dataclass
from time import sleep

from raspirobot.audio import AudioListenWorker
from shared.logging_utils import log_event

from .event_bus import EventBus
from .events import RuntimeEvent, RuntimeEventType
from .state_machine import RobotEvent, RobotRuntimeState, RobotStateMachine
from .turn_manager import TurnManager, TurnResult, UtteranceRejected


@dataclass
class RuntimeLoopResult:
    handled: bool
    state: RobotRuntimeState
    turn: TurnResult | None = None
    error: str | None = None


class RaspiRobotRuntime:
    def __init__(
        self,
        *,
        listener: AudioListenWorker,
        turn_manager: TurnManager,
        state_machine: RobotStateMachine | None = None,
        event_bus: EventBus | None = None,
        loop_sleep_seconds: float = 0.05,
        post_playback_cooldown_ms: int = 0,
    ) -> None:
        self.listener = listener
        self.turn_manager = turn_manager
        self.state_machine = state_machine or RobotStateMachine()
        self.event_bus = event_bus or EventBus()
        self.loop_sleep_seconds = loop_sleep_seconds
        self.post_playback_cooldown_ms = post_playback_cooldown_ms
        self._ensure_listening()

    def run_once(self) -> RuntimeLoopResult:
        if not self.state_machine.can_accept_speech():
            self.state_machine.transition(RobotEvent.NEW_SPEECH_INPUT)
            return RuntimeLoopResult(handled=False, state=self.state_machine.state)

        utterance = self.listener.listen_once()
        if utterance is None:
            return RuntimeLoopResult(handled=False, state=self.state_machine.state)

        self.event_bus.publish(RuntimeEvent(RuntimeEventType.SPEECH_STARTED))
        self.state_machine.transition(RobotEvent.SPEECH_START)
        self.state_machine.transition(RobotEvent.SPEECH_END, turn_id=utterance.wav_path.name)
        self.event_bus.publish(
            RuntimeEvent(
                RuntimeEventType.UTTERANCE_READY,
                {
                    "wav_path": str(utterance.wav_path),
                    "duration_ms": utterance.duration_ms,
                },
            )
        )

        try:
            self.event_bus.publish(RuntimeEvent(RuntimeEventType.REMOTE_REQUEST_STARTED))
            self.state_machine.transition(RobotEvent.REMOTE_REQUEST_SENT)
            turn = self.turn_manager.handle_utterance(
                utterance.wav_path,
                state=self.state_machine.state.value,
                before_playback=self._mark_remote_result_ready,
            )
            self.event_bus.publish(RuntimeEvent(RuntimeEventType.ROBOT_ACTION_RECEIVED))
            self.event_bus.publish(RuntimeEvent(RuntimeEventType.PLAYBACK_DONE))
            self.state_machine.transition(RobotEvent.PLAYBACK_DONE)
            
            # Apply post-playback cooldown if configured
            if self.post_playback_cooldown_ms > 0:
                log_event(
                    "playback_cooldown_started",
                    cooldown_ms=self.post_playback_cooldown_ms,
                )
                sleep(self.post_playback_cooldown_ms / 1000.0)
                log_event(
                    "playback_cooldown_done",
                    cooldown_ms=self.post_playback_cooldown_ms,
                )
            
            return RuntimeLoopResult(handled=True, state=self.state_machine.state, turn=turn)
        except UtteranceRejected as exc:
            log_event(
                "utterance_rejected_at_runtime",
                wav_path=str(exc.wav_path),
                reason=exc.reason,
            )
            self.event_bus.publish(RuntimeEvent(RuntimeEventType.SPEECH_ENDED))
            self.state_machine.transition(RobotEvent.UTTERANCE_REJECTED)
            return RuntimeLoopResult(handled=False, state=self.state_machine.state)
        except Exception as exc:
            message = str(exc)
            self.event_bus.publish(RuntimeEvent(RuntimeEventType.REMOTE_REQUEST_FAILED, {"error": message}))
            self.state_machine.transition(RobotEvent.SYSTEM_ERROR, error=message)
            return RuntimeLoopResult(handled=False, state=self.state_machine.state, error=message)

    def run_forever(self) -> None:
        while True:
            result = self.run_once()
            if result.state == RobotRuntimeState.ERROR_FALLBACK:
                self.state_machine.transition(RobotEvent.RECOVERY_DONE)
            sleep(self.loop_sleep_seconds)

    def _ensure_listening(self) -> None:
        if self.state_machine.state == RobotRuntimeState.IDLE:
            self.state_machine.transition(RobotEvent.WAKE_WORD_DETECTED)
            self.state_machine.transition(RobotEvent.WAKE_ACK_DONE)

    def _mark_remote_result_ready(self, response) -> None:
        self.event_bus.publish(
            RuntimeEvent(
                RuntimeEventType.REMOTE_RESULT_READY,
                {
                    "turn_id": response.turn_id,
                    "success": response.success,
                },
            )
        )
        self.state_machine.transition(RobotEvent.REMOTE_RESULT_READY)
        self.event_bus.publish(RuntimeEvent(RuntimeEventType.PLAYBACK_STARTED))
        self.state_machine.transition(RobotEvent.PLAYBACK_STARTED)
