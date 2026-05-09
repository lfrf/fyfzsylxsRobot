from __future__ import annotations

from dataclasses import dataclass
from time import monotonic, sleep
from typing import Any

from raspirobot.audio import AudioListenWorker, ListenResult
from shared.logging_utils import log_event

from .event_bus import EventBus
from .events import RuntimeEvent, RuntimeEventType
from .state_machine import RobotEvent, RobotRuntimeState, RobotStateMachine
from .turn_manager import TurnManager, TurnResult, UtteranceRejected


STANDBY_PROMPT_TEXT = "我先休息啦，需要我时再叫我。"


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
        self._pending_working_utterance: Any | None = None
        self._strict_listening_until: float = 0.0
        self._preparing_vision_epoch_active = False
        self._ensure_initial_state()

    def run_once(self) -> RuntimeLoopResult:
        if self.state_machine.state == RobotRuntimeState.STANDBY:
            return self._run_standby_once()
        if self.state_machine.state == RobotRuntimeState.PREPARING:
            return self._run_preparing_once()
        if self.state_machine.state in {
            RobotRuntimeState.WORKING,
            RobotRuntimeState.LISTENING,
            RobotRuntimeState.RECORDING,
            RobotRuntimeState.UPLOADING,
            RobotRuntimeState.THINKING,
            RobotRuntimeState.SPEAKING,
        }:
            return self._run_working_once()
        if self.state_machine.state == RobotRuntimeState.ERROR_FALLBACK:
            # Non-fatal remote failures should recover to WORKING/LISTENING without impacting visual lifecycle.
            self.state_machine.transition(RobotEvent.RECOVERY_DONE)
            if self.state_machine.state != RobotRuntimeState.STANDBY:
                self._enter_working_listening()
            return RuntimeLoopResult(handled=False, state=self.state_machine.state)
        return RuntimeLoopResult(handled=False, state=self.state_machine.state)

    def _run_standby_once(self) -> RuntimeLoopResult:
        self._start_wake_word_provider()
        if self.wake_word_provider is not None and self.wake_word_provider.poll():
            log_event("wake_word_triggered")
            self._stop_wake_word_provider()
            self.state_machine.transition(RobotEvent.WAKE_WORD_DETECTED)
            self._enter_preparing()
        return RuntimeLoopResult(handled=False, state=self.state_machine.state)

    def _run_preparing_once(self) -> RuntimeLoopResult:
        self._enter_preparing()
        # Give the camera/vision upload thread a short window to publish frames
        # before asking the remote side to resolve face identity.
        prepare_wait_seconds = float(getattr(self.turn_manager.settings, "prepare_face_wait_seconds", 3.0) or 3.0)
        if prepare_wait_seconds > 0:
            sleep(min(prepare_wait_seconds, 3.0))

        try:
            prepare_result = self.turn_manager.handle_prepare_user(turn_id="prepare")
        except Exception as exc:
            log_event("prepare_user_failed", error=str(exc), level="error")
            self._complete_preparing()
            return RuntimeLoopResult(handled=False, state=self.state_machine.state, error=str(exc))

        if prepare_result.needs_username_registration and prepare_result.user_id:
            username_timeout = float(
                getattr(self.turn_manager.settings, "username_reply_timeout_seconds", 10.0) or 10.0
            )
            log_event(
                "username_registration_listening_started",
                user_id=prepare_result.user_id,
                timeout_seconds=username_timeout,
            )
            username_result = self._listen_once_with_recovery(
                speech_start_timeout_seconds=username_timeout,
                context="username_registration",
            )
            if username_result.kind == "utterance" and username_result.utterance is not None:
                try:
                    self.turn_manager.handle_username_utterance(
                        username_result.utterance.wav_path,
                        user_id=prepare_result.user_id,
                        turn_id="username",
                    )
                except Exception as exc:
                    log_event("register_username_failed", user_id=prepare_result.user_id, error=str(exc), level="error")
            elif username_result.kind == "timeout":
                log_event(
                    "username_registration_timeout",
                    user_id=prepare_result.user_id,
                    timeout_seconds=username_timeout,
                )
            else:
                log_event(
                    "username_registration_capture_unavailable",
                    user_id=prepare_result.user_id,
                    listen_result=username_result.kind,
                    error=username_result.error,
                    level="error",
                )

        self._mark_post_playback_strict_window()
        first_result = self._listen_once_with_recovery(
            speech_start_timeout_seconds=self.work_idle_timeout_seconds,
            context="preparing_first_speech",
        )
        if first_result.kind == "timeout":
            log_event(
                "preparing_first_speech_timeout",
                timeout_seconds=self.work_idle_timeout_seconds,
            )
            self.state_machine.transition(RobotEvent.WORK_IDLE_TIMEOUT)
            self._exit_to_standby()
            return RuntimeLoopResult(handled=False, state=self.state_machine.state)
        if first_result.kind != "utterance" or first_result.utterance is None:
            log_event(
                "preparing_first_speech_capture_unavailable",
                listen_result=first_result.kind,
                error=first_result.error,
                level="error",
            )
            self.state_machine.transition(RobotEvent.SYSTEM_ERROR, error=first_result.error or first_result.kind)
            self.state_machine.transition(RobotEvent.RECOVERY_DONE)
            return RuntimeLoopResult(handled=False, state=self.state_machine.state, error=first_result.error)

        first_utterance = first_result.utterance
        log_event(
            "preparing_first_speech_ready",
            wav_path=str(first_utterance.wav_path),
            duration_ms=first_utterance.duration_ms,
        )
        self._pending_working_utterance = first_utterance
        self._complete_preparing()
        return RuntimeLoopResult(handled=False, state=self.state_machine.state)

    def _run_working_once(self) -> RuntimeLoopResult:
        self._enter_working_listening()
        if self._pending_working_utterance is not None:
            utterance = self._pending_working_utterance
            self._pending_working_utterance = None
            log_event(
                "working_pending_utterance_consumed",
                wav_path=str(utterance.wav_path),
                duration_ms=utterance.duration_ms,
            )
        else:
            speech_start_timeout = self.work_idle_timeout_seconds if self.wake_word_provider is not None else None
            listen_result = self._listen_once_with_recovery(
                speech_start_timeout_seconds=speech_start_timeout,
                context="working",
            )
            if listen_result.kind == "timeout":
                log_event(
                    "work_idle_timeout",
                    timeout_seconds=self.work_idle_timeout_seconds,
                )
                self.state_machine.transition(RobotEvent.WORK_IDLE_TIMEOUT)
                self._exit_to_standby()
                return RuntimeLoopResult(handled=False, state=self.state_machine.state)
            if listen_result.kind != "utterance" or listen_result.utterance is None:
                log_event(
                    "working_audio_capture_unavailable",
                    listen_result=listen_result.kind,
                    error=listen_result.error,
                    returncode=listen_result.returncode,
                    elapsed_ms=listen_result.elapsed_ms,
                    frames_emitted=listen_result.frames_emitted,
                    level="error",
                )
                self.state_machine.transition(RobotEvent.SYSTEM_ERROR, error=listen_result.error or listen_result.kind)
                self.state_machine.transition(RobotEvent.RECOVERY_DONE)
                self._enter_working_listening()
                return RuntimeLoopResult(handled=False, state=self.state_machine.state, error=listen_result.error)
            utterance = listen_result.utterance

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

            self._mark_post_playback_strict_window()
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
            log_event("remote_request_nonfatal_error", error=message)
            # Keep visual lifecycle alive and continue working loop.
            self.state_machine.transition(RobotEvent.SYSTEM_ERROR, error=message)
            self.state_machine.transition(RobotEvent.RECOVERY_DONE)
            self._enter_working_listening()
            return RuntimeLoopResult(handled=False, state=self.state_machine.state, error=message)

    def _listen_once_with_recovery(
        self,
        *,
        speech_start_timeout_seconds: float | None,
        context: str,
    ) -> ListenResult:
        settings = getattr(self.turn_manager, "settings", None)
        retry_count = max(0, int(getattr(settings, "audio_capture_retry_count", 2) or 0))
        retry_cooldown_ms = max(0, int(getattr(settings, "audio_capture_retry_cooldown_ms", 700) or 0))
        attempts = retry_count + 1
        last_result: ListenResult | None = None
        for attempt_index in range(attempts):
            settings = getattr(self.turn_manager, "settings", None)
            strict_active = monotonic() < self._strict_listening_until
            rms_threshold_override = None
            speech_start_frames_override = None
            if strict_active:
                rms_threshold_override = max(
                    float(getattr(settings, "vad_rms_threshold", 0) or 0),
                    float(getattr(settings, "vad_post_playback_rms_threshold", 1400) or 1400),
                )
                speech_start_frames_override = max(
                    int(getattr(settings, "vad_speech_start_frames", 1) or 1),
                    int(getattr(settings, "vad_post_playback_speech_start_frames", 10) or 10),
                )
                log_event(
                    "post_playback_strict_vad_active",
                    context=context,
                    rms_threshold=rms_threshold_override,
                    speech_start_frames=speech_start_frames_override,
                )
            result = self.listener.listen_once_result(
                speech_start_timeout_seconds=speech_start_timeout_seconds,
                rms_threshold_override=rms_threshold_override,
                speech_start_frames_override=speech_start_frames_override,
                dynamic_noise_enabled=bool(getattr(settings, "vad_dynamic_noise_enabled", True)),
                dynamic_noise_calibration_ms=int(getattr(settings, "vad_dynamic_noise_calibration_ms", 500) or 0),
                dynamic_noise_ratio=float(getattr(settings, "vad_dynamic_noise_ratio", 2.2) or 2.2),
            )
            if result.kind in {"utterance", "timeout"}:
                return result
            last_result = result
            log_event(
                "audio_listen_recoverable_error",
                context=context,
                attempt_index=attempt_index + 1,
                attempts=attempts,
                listen_result=result.kind,
                error=result.error,
                returncode=result.returncode,
                elapsed_ms=result.elapsed_ms,
                frames_emitted=result.frames_emitted,
                stderr_tail=result.stderr_tail,
                level="error",
            )
            if attempt_index < retry_count and retry_cooldown_ms > 0:
                sleep(retry_cooldown_ms / 1000.0)
        return last_result or ListenResult(kind="capture_error", error="listen failed before producing a result")

    def _mark_post_playback_strict_window(self) -> None:
        settings = getattr(self.turn_manager, "settings", None)
        strict_ms = max(0, int(getattr(settings, "vad_post_playback_strict_ms", 2500) or 0))
        if strict_ms <= 0:
            return
        self._strict_listening_until = monotonic() + strict_ms / 1000.0
        log_event("post_playback_strict_vad_window_started", strict_ms=strict_ms)

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
        self._exit_to_standby()

    def _enter_preparing(self) -> None:
        if not self._preparing_vision_epoch_active:
            self._begin_vision_fresh_epoch("preparing")
            self._preparing_vision_epoch_active = True
        if self.state_machine.state != RobotRuntimeState.PREPARING:
            self.state_machine.state = RobotRuntimeState.PREPARING
            log_event("preparing_started")
        # Wake visual feedback must happen before face tracking starts, otherwise
        # the first face-tracking frames can still be accompanied by sleep eyes.
        self._set_eyes("listening")
        log_event("preparing_eyes_ready", expression="listening")
        self._start_face_tracking()
        log_event("preparing_done")

    def _complete_preparing(self) -> None:
        self.state_machine.transition(RobotEvent.WAKE_ACK_DONE)
        self._enter_working_listening()

    def _enter_working_listening(self) -> None:
        self.state_machine.state = RobotRuntimeState.WORKING
        self._stop_wake_word_provider()
        self._set_eyes("listening")
        log_event("working_listening_ready")

    def _exit_to_standby(self) -> None:
        self._stop_face_tracking()
        self._reset_vision_provider("standby")
        self._preparing_vision_epoch_active = False
        log_event("standby_prompt", text=STANDBY_PROMPT_TEXT)
        self._set_eyes("sleep")
        self._start_wake_word_provider()
        self.state_machine.state = RobotRuntimeState.STANDBY

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

    def _vision_provider(self):
        return getattr(self.turn_manager.payload_builder, "vision_context_provider", None)

    def _begin_vision_fresh_epoch(self, reason: str) -> None:
        provider = self._vision_provider()
        if provider is None or not hasattr(provider, "begin_fresh_epoch"):
            return
        try:
            provider.begin_fresh_epoch(reason=reason)
        except Exception as exc:
            log_event("remote_vision_fresh_epoch_start_failed", reason=reason, error=str(exc), level="warning")

    def _reset_vision_provider(self, reason: str) -> None:
        provider = self._vision_provider()
        if provider is None or not hasattr(provider, "reset"):
            return
        try:
            provider.reset(reason=reason)
        except Exception as exc:
            log_event("remote_vision_provider_reset_failed", reason=reason, error=str(exc), level="warning")

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
