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
        wake_word_provider=None,
        work_idle_timeout_seconds: float = 10.0,
        face_tracking_lifecycle=None,
        eyes_driver=None,
    ) -> None:
        self.listener = listener
        self.turn_manager = turn_manager
        self.state_machine = state_machine or RobotStateMachine()
        self.event_bus = event_bus or EventBus()
        self.loop_sleep_seconds = loop_sleep_seconds
        self.post_playback_cooldown_ms = post_playback_cooldown_ms
        self.wake_word_provider = wake_word_provider
        self.work_idle_timeout_seconds = work_idle_timeout_seconds
        self.face_tracking_lifecycle = face_tracking_lifecycle
        self.eyes_driver = eyes_driver
        self._ensure_initial_state()

    def run_once(self) -> RuntimeLoopResult:
        # 待机模式：等待唤醒词
        if self.state_machine.state == RobotRuntimeState.STANDBY:
            self._start_wake_word_provider()
            if self.wake_word_provider is not None and self.wake_word_provider.poll():
                log_event("wake_word_triggered")
                self._stop_wake_word_provider()
                self._start_face_tracking()
                self.state_machine.transition(RobotEvent.WAKE_WORD_DETECTED)
                self.state_machine.transition(RobotEvent.WAKE_ACK_DONE)
                self._set_eyes("listening")
            return RuntimeLoopResult(handled=False, state=self.state_machine.state)

        if not self.state_machine.can_accept_speech():
            self.state_machine.transition(RobotEvent.NEW_SPEECH_INPUT)
            return RuntimeLoopResult(handled=False, state=self.state_machine.state)

        self._stop_wake_word_provider()
        speech_start_timeout = self.work_idle_timeout_seconds if self.wake_word_provider is not None else None
        utterance = self.listener.listen_once(speech_start_timeout_seconds=speech_start_timeout)
        if utterance is None:
            if self.wake_word_provider is not None:
                log_event(
                    "work_idle_timeout",
                    timeout_seconds=self.work_idle_timeout_seconds,
                )
                self.state_machine.transition(RobotEvent.WORK_IDLE_TIMEOUT)
                self._enter_standby()
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

    def _ensure_initial_state(self) -> None:
        """根据是否有唤醒词引擎决定初始状态。"""
        if self.wake_word_provider is not None:
            # 有唤醒词引擎：进入 STANDBY 待机
            if self.state_machine.state == RobotRuntimeState.IDLE:
                self.state_machine.state = RobotRuntimeState.STANDBY
                self._enter_standby()
                log_event("wake_word_standby_mode_enabled")
        else:
            # 无唤醒词引擎：直接进入 LISTENING（原有行为）
            self._ensure_listening()

    def _ensure_listening(self) -> None:
        if self.state_machine.state == RobotRuntimeState.IDLE:
            self.state_machine.transition(RobotEvent.WAKE_WORD_DETECTED)
            self.state_machine.transition(RobotEvent.WAKE_ACK_DONE)

    def _set_eyes(self, expression: str) -> None:
        if self.eyes_driver is not None:
            try:
                self.eyes_driver.set_expression(expression)
            except Exception as exc:
                log_event("eyes_set_expression_failed", expression=expression, error=str(exc))

    def _enter_standby(self) -> None:
        self._stop_face_tracking()
        self._set_eyes("sleep")
        self._start_wake_word_provider()

    def _start_wake_word_provider(self) -> None:
        if self.wake_word_provider is None:
            return
        try:
            self.wake_word_provider.start()
        except Exception as exc:
            log_event("wake_word_start_failed", error=str(exc), level="error")

    def _stop_wake_word_provider(self) -> None:
        if self.wake_word_provider is None:
            return
        try:
            self.wake_word_provider.stop()
        except Exception as exc:
            log_event("wake_word_stop_failed", error=str(exc), level="error")

    def _start_face_tracking(self) -> None:
        if self.face_tracking_lifecycle is None:
            return
        try:
            self.face_tracking_lifecycle.start()
        except Exception as exc:
            log_event("face_tracking_start_failed", error=str(exc), level="error")

    def _stop_face_tracking(self) -> None:
        if self.face_tracking_lifecycle is None:
            return
        try:
            self.face_tracking_lifecycle.stop()
        except Exception as exc:
            log_event("face_tracking_stop_failed", error=str(exc), level="error")

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
