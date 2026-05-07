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
        identity_watcher=None,
        vision_lifecycle=None,
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
        self.identity_watcher = identity_watcher
        self.vision_lifecycle = vision_lifecycle
        self.eyes_driver = eyes_driver
        self._tracking_face_id: str | None = None
        self._ensure_initial_state()

    def run_once(self) -> RuntimeLoopResult:
        # 待机模式：等待唤醒词
        if self.state_machine.state == RobotRuntimeState.STANDBY:
            self._start_wake_word_provider()
            if self.wake_word_provider is not None and self.wake_word_provider.poll():
                log_event("wake_word_triggered")
                self._stop_wake_word_provider()
                self._start_vision_provider(shared_camera_mode=False)
                self._start_identity_watcher(shared_camera_mode=False)
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
        self._clear_active_face_identity()
        self._stop_identity_watcher()
        self._stop_face_tracking()
        self._stop_vision_provider()
        self._set_eyes("sleep")
        self._start_wake_word_provider()

    def handle_identity_resolved(self, face_identity, result) -> None:
        face_id = str(getattr(result, "face_id", None) or getattr(face_identity, "face_id", "") or "").strip()
        if not face_id:
            return
        if self.state_machine.state == RobotRuntimeState.STANDBY:
            return
        if self._tracking_face_id == face_id:
            return
        self._set_active_face_identity(face_id)

        switched_to_shared_camera = False
        if self.identity_watcher is not None and self.face_tracking_lifecycle is not None:
            try:
                self._start_vision_provider(shared_camera_mode=True)
                switched_to_shared_camera = True
            except Exception as exc:
                log_event("vision_shared_camera_switch_failed", face_id=face_id, error=str(exc), level="error")
        if self._start_face_tracking():
            self._tracking_face_id = face_id
            log_event(
                "face_tracking_enabled_after_identity",
                face_id=face_id,
                user_id=getattr(result, "user_id", None),
                persisted=bool(getattr(result, "persisted", False)),
            )
        elif switched_to_shared_camera and self.identity_watcher is not None:
            try:
                self._start_vision_provider(shared_camera_mode=False)
            except Exception as exc:
                log_event("vision_own_camera_restore_failed", face_id=face_id, error=str(exc), level="error")

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

    def _start_face_tracking(self) -> bool:
        if self.face_tracking_lifecycle is None:
            return False
        try:
            started = self.face_tracking_lifecycle.start()
            if started is False:
                log_event("face_tracking_start_skipped_or_failed", level="warning")
                return False
            return True
        except Exception as exc:
            log_event("face_tracking_start_failed", error=str(exc), level="error")
            return False

    def _stop_face_tracking(self) -> None:
        if self.face_tracking_lifecycle is None:
            return
        try:
            self.face_tracking_lifecycle.stop()
            self._tracking_face_id = None
        except Exception as exc:
            log_event("face_tracking_stop_failed", error=str(exc), level="error")

    def _start_identity_watcher(self, *, shared_camera_mode: bool) -> None:
        if self.identity_watcher is None:
            return
        try:
            self.identity_watcher.start(shared_camera_mode=shared_camera_mode)
        except Exception as exc:
            log_event("identity_watcher_start_failed", error=str(exc), level="error")

    def _stop_identity_watcher(self) -> None:
        if self.identity_watcher is None:
            return
        try:
            self.identity_watcher.stop()
        except Exception as exc:
            log_event("identity_watcher_stop_failed", error=str(exc), level="error")

    def _start_vision_provider(self, *, shared_camera_mode: bool) -> None:
        if self.vision_lifecycle is None:
            return
        try:
            if hasattr(self.vision_lifecycle, "stop"):
                self.vision_lifecycle.stop()
            if hasattr(self.vision_lifecycle, "set_shared_camera_mode"):
                self.vision_lifecycle.set_shared_camera_mode(shared_camera_mode)
            if hasattr(self.vision_lifecycle, "start"):
                self.vision_lifecycle.start()
            log_event(
                "vision_provider_started_for_work_mode",
                shared_camera_mode=shared_camera_mode,
            )
        except Exception as exc:
            log_event("vision_provider_start_failed", shared_camera_mode=shared_camera_mode, error=str(exc), level="error")

    def _stop_vision_provider(self) -> None:
        if self.vision_lifecycle is None:
            return
        try:
            self.vision_lifecycle.stop()
            log_event("vision_provider_stopped_for_standby")
        except Exception as exc:
            log_event("vision_provider_stop_failed", error=str(exc), level="error")

    def _set_active_face_identity(self, face_id: str) -> None:
        try:
            self.turn_manager.payload_builder.request_options["face_id"] = face_id
        except Exception as exc:
            log_event("active_face_identity_set_failed", face_id=face_id, error=str(exc), level="warning")

    def _clear_active_face_identity(self) -> None:
        try:
            self.turn_manager.payload_builder.request_options.pop("face_id", None)
        except Exception as exc:
            log_event("active_face_identity_clear_failed", error=str(exc), level="warning")

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
